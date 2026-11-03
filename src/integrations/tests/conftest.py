import json

import pytest
from django.contrib.auth.models import Permission


class FakeResponse:
    def __init__(self, body=None, status_code=200):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)
        self.content = b'' if body is None else self.text.encode()

    def json(self):
        if self._body is None:
            raise ValueError('no body')
        return self._body


class FakeService:
    """Routes requests.Session.request calls by method and path (after the /api/v3 prefix)."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def on(self, method, path, body=None, status_code=200):
        self.routes[(method, path)] = FakeResponse(body, status_code)

    def calls_to(self, method, path):
        return [call for call in self.calls if call['method'] == method and call['path'] == path]

    def __call__(self, session, method, url, **kwargs):
        path = url.split('/api/v3', 1)[1]
        self.calls.append({'method': method, 'path': path, 'url': url, 'headers': dict(session.headers), 'verify': session.verify, **kwargs})
        return self.routes[(method, path)]


@pytest.fixture
def arr_settings(settings):
    settings.RADARR_URL = 'http://radarr.test:7878'
    settings.RADARR_API_KEY = 'radarr-key'
    settings.RADARR_PUBLIC_URL = settings.RADARR_URL
    settings.RADARR_VERIFY_SSL = True
    settings.SONARR_URL = 'http://sonarr.test:8989'
    settings.SONARR_API_KEY = 'sonarr-key'
    settings.SONARR_PUBLIC_URL = settings.SONARR_URL
    settings.SONARR_VERIFY_SSL = True
    return settings


@pytest.fixture
def fake_arr(mocker):
    service = FakeService()
    mocker.patch('requests.Session.request', autospec=True, side_effect=service)
    return service


@pytest.fixture
def arr_user(user):
    user.user_permissions.add(Permission.objects.get(codename='use_sonarr_radarr'))
    return user


@pytest.fixture
def arr_client(api_client, arr_user, arr_settings):
    api_client.force_authenticate(user=arr_user)
    return api_client
