import importlib

import pytest

from arxmedia.settings import integrations as integration_settings

SERVICES = ['RADARR', 'SONARR']


@pytest.fixture
def reload_settings(monkeypatch):
    def reload(**env):
        for service in SERVICES:
            for suffix in ('URL', 'API_KEY', 'PUBLIC_URL', 'VERIFY_SSL'):
                monkeypatch.delenv(f'{service}_{suffix}', raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(integration_settings)

    yield reload
    monkeypatch.undo()
    importlib.reload(integration_settings)


@pytest.mark.parametrize('service', SERVICES)
class TestArrSettings:
    def test_public_url_defaults_to_the_service_url(self, reload_settings, service):
        module = reload_settings(**{f'{service}_URL': 'http://arr:7878/'})

        assert getattr(module, f'{service}_URL') == 'http://arr:7878'
        assert getattr(module, f'{service}_PUBLIC_URL') == 'http://arr:7878'

    def test_explicit_public_url_wins(self, reload_settings, service):
        module = reload_settings(**{f'{service}_URL': 'http://arr:7878', f'{service}_PUBLIC_URL': 'https://arr.example.com/'})

        assert getattr(module, f'{service}_PUBLIC_URL') == 'https://arr.example.com'

    def test_unconfigured_by_default(self, reload_settings, service):
        module = reload_settings()

        values = (getattr(module, f'{service}_{suffix}') for suffix in ('URL', 'API_KEY', 'PUBLIC_URL'))
        assert tuple(values) == ('', '', '')

    @pytest.mark.parametrize(('value', 'expected'), [('False', False), ('0', False), ('no', False), ('True', True), ('', True)])
    def test_verify_ssl_flag(self, reload_settings, service, value, expected):
        module = reload_settings(**{f'{service}_VERIFY_SSL': value})

        assert getattr(module, f'{service}_VERIFY_SSL') is expected

    def test_verify_ssl_is_on_when_unset(self, reload_settings, service):
        assert getattr(reload_settings(), f'{service}_VERIFY_SSL') is True
