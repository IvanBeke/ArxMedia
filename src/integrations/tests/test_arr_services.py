from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
import requests
from django.urls import reverse


class ArrService(NamedTuple):
    name: str
    settings_prefix: str
    options_url: str
    item_url: str
    base_url: str
    api_key: str
    root_folder: str


SERVICES = [
    ArrService(
        'Radarr', 'RADARR', reverse('radarr_options'), reverse('radarr_movie', args=[603]),
        'http://radarr.test:7878', 'radarr-key', '/movies',
    ),
    ArrService(
        'Sonarr', 'SONARR', reverse('sonarr_options'), reverse('sonarr_series', args=[1396]),
        'http://sonarr.test:8989', 'sonarr-key', '/tv',
    ),
]


@pytest.fixture(params=SERVICES, ids=lambda service: service.name)
def service(request):
    return request.param


@pytest.fixture(params=['options_url', 'item_url'])
def endpoint(request, service):
    return getattr(service, request.param)


@pytest.fixture
def options_routes(fake_arr, service):
    fake_arr.on('GET', '/rootfolder', [{'id': 1, 'path': service.root_folder, 'freeSpace': 1000, 'accessible': True}])
    fake_arr.on('GET', '/qualityprofile', [{'id': 4, 'name': 'HD-1080p', 'cutoff': 7}])
    fake_arr.on('GET', '/tag', [{'id': 2, 'label': 'kids'}])
    return fake_arr


class TestPermissionGate:
    def test_anonymous_gets_401(self, api_client, arr_settings, endpoint):
        assert api_client.get(endpoint).status_code == 401

    def test_user_without_permission_gets_403(self, auth_client, arr_settings, endpoint):
        assert auth_client.get(endpoint).status_code == 403

    def test_write_methods_without_permission_get_403(self, auth_client, arr_settings, service):
        assert auth_client.post(service.item_url, {}, format='json').status_code == 403
        assert auth_client.delete(service.item_url, {}, format='json').status_code == 403

    def test_superuser_is_allowed(self, api_client, user, arr_settings, service, options_routes):
        user.is_superuser = True
        user.save()
        api_client.force_authenticate(user=user)

        assert api_client.get(service.options_url).status_code == 200


class TestUnconfigured:
    def test_returns_503_when_the_service_is_not_configured(self, api_client, arr_user, settings, service, endpoint):
        setattr(settings, f'{service.settings_prefix}_URL', '')
        setattr(settings, f'{service.settings_prefix}_API_KEY', '')
        api_client.force_authenticate(user=arr_user)

        response = api_client.get(endpoint)

        assert response.status_code == 503
        assert response.data['detail'] == f'{service.name} is not configured.'


class TestOptions:
    def test_returns_normalized_options_using_the_service_credentials(self, arr_client, service, options_routes):
        response = arr_client.get(service.options_url)

        assert response.status_code == 200
        assert response.data == {
            'root_folders': [{'path': service.root_folder, 'free_space': 1000}],
            'quality_profiles': [{'id': 4, 'name': 'HD-1080p'}],
            'tags': [{'id': 2, 'label': 'kids'}],
        }
        assert options_routes.calls[0]['headers']['X-Api-Key'] == service.api_key
        assert options_routes.calls[0]['host'] == urlsplit(service.base_url).netloc


class TestUpstreamFailures:
    def test_unreachable_service_returns_502(self, arr_client, service, mocker):
        mocker.patch('requests.Session.request', side_effect=requests.ConnectionError('refused'))

        response = arr_client.get(service.options_url)

        assert response.status_code == 502
        assert response.data['detail'] == f'Could not reach {service.name}.'

    def test_rejected_api_key_returns_502(self, arr_client, service, fake_arr):
        fake_arr.on('GET', '/rootfolder', {'error': 'Unauthorized'}, status_code=401)

        response = arr_client.get(service.options_url)

        assert response.status_code == 502
        assert response.data['detail'] == f'{service.name} rejected the API key.'

    def test_server_error_returns_502(self, arr_client, service, fake_arr):
        fake_arr.on('GET', '/rootfolder', None, status_code=500)

        response = arr_client.get(service.options_url)

        assert response.status_code == 502
        assert 'HTTP 500' in response.data['detail']


class TestSslVerification:
    def test_verifies_certificates_by_default(self, arr_client, service, options_routes):
        arr_client.get(service.options_url)

        assert options_routes.calls[0]['verify'] is True

    def test_verification_can_be_disabled_for_self_signed_certificates(
        self, arr_client, arr_settings, service, options_routes,
    ):
        setattr(arr_settings, f'{service.settings_prefix}_VERIFY_SSL', False)

        arr_client.get(service.options_url)

        assert options_routes.calls[0]['verify'] is False
