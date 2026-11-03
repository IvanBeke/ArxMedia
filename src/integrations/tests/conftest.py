import json
from urllib.parse import urlsplit

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
    """Routes requests.Session.request calls by method and URL path (without the /api/v3 prefix)."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def on(self, method, path, body=None, status_code=200):
        """Register a response; a callable body receives the request params and returns the JSON body."""
        self.routes[(method, path)] = body if callable(body) else FakeResponse(body, status_code)

    def calls_to(self, method, path):
        return [call for call in self.calls if call['method'] == method and call['path'] == path]

    def __call__(self, session, method, url, **kwargs):
        parts = urlsplit(url)
        path = parts.path.removeprefix('/api/v3')
        self.calls.append({
            'method': method, 'path': path, 'url': url, 'host': parts.netloc,
            'headers': dict(session.headers), 'verify': session.verify, **kwargs,
        })
        route = self.routes[(method, path)]
        return FakeResponse(route(kwargs.get('params') or {})) if callable(route) else route


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


@pytest.fixture
def jellyfin_settings(settings):
    settings.JELLYFIN_URL = 'http://jellyfin.test:8096'
    settings.JELLYFIN_API_KEY = 'jellyfin-key'
    settings.JELLYFIN_PUBLIC_URL = settings.JELLYFIN_URL
    settings.JELLYFIN_VERIFY_SSL = True
    return settings


@pytest.fixture
def jellyfin_user(user):
    user.user_permissions.add(Permission.objects.get(codename='use_jellyfin'))
    return user


@pytest.fixture
def jellyfin_api(api_client, jellyfin_user, jellyfin_settings):
    api_client.force_authenticate(user=jellyfin_user)
    return api_client
