import importlib

import pytest

from arxmedia.settings import integrations as integration_settings


@pytest.fixture
def reload_settings(monkeypatch):
    def reload(**env):
        for name in ('RADARR_URL', 'RADARR_API_KEY', 'RADARR_PUBLIC_URL', 'RADARR_VERIFY_SSL'):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(integration_settings)

    yield reload
    monkeypatch.undo()
    importlib.reload(integration_settings)


class TestRadarrSettings:
    def test_public_url_defaults_to_the_service_url(self, reload_settings):
        module = reload_settings(RADARR_URL='http://radarr:7878/')

        assert module.RADARR_URL == 'http://radarr:7878'
        assert module.RADARR_PUBLIC_URL == 'http://radarr:7878'

    def test_explicit_public_url_wins(self, reload_settings):
        module = reload_settings(RADARR_URL='http://radarr:7878', RADARR_PUBLIC_URL='https://radarr.example.com/')

        assert module.RADARR_PUBLIC_URL == 'https://radarr.example.com'

    def test_unconfigured_by_default(self, reload_settings):
        module = reload_settings()

        assert (module.RADARR_URL, module.RADARR_API_KEY, module.RADARR_PUBLIC_URL) == ('', '', '')

    @pytest.mark.parametrize(('value', 'expected'), [('False', False), ('0', False), ('no', False), ('True', True), ('', True)])
    def test_verify_ssl_flag(self, reload_settings, value, expected):
        assert reload_settings(RADARR_VERIFY_SSL=value).RADARR_VERIFY_SSL is expected

    def test_verify_ssl_is_on_when_unset(self, reload_settings):
        assert reload_settings().RADARR_VERIFY_SSL is True
