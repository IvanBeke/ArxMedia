import pytest
from django.urls import reverse

ME_URL = reverse('me')
NO_FLAGS = {'radarr': False, 'sonarr': False, 'jellyfin': False}


@pytest.mark.django_db
class TestMeIntegrationFlags:
    def test_all_flags_are_false_without_permission(self, auth_client, arr_settings, jellyfin_settings):
        assert auth_client.get(ME_URL).data['integrations'] == NO_FLAGS

    @pytest.mark.parametrize('service', ['radarr', 'sonarr'])
    def test_arr_flag_requires_configuration(self, api_client, arr_user, settings, service):
        setattr(settings, f'{service.upper()}_URL', '')
        setattr(settings, f'{service.upper()}_API_KEY', '')
        api_client.force_authenticate(user=arr_user)

        assert api_client.get(ME_URL).data['integrations'][service] is False

    def test_arr_flags_are_true_with_permission_and_configuration(self, arr_client, jellyfin_settings):
        assert arr_client.get(ME_URL).data['integrations'] == {'radarr': True, 'sonarr': True, 'jellyfin': False}

    def test_services_are_flagged_independently(self, arr_client, arr_settings):
        arr_settings.SONARR_URL = ''

        assert arr_client.get(ME_URL).data['integrations'] == {'radarr': True, 'sonarr': False, 'jellyfin': False}

    def test_jellyfin_flag_needs_its_own_permission_and_configuration(self, jellyfin_api, jellyfin_settings, arr_settings):
        assert jellyfin_api.get(ME_URL).data['integrations'] == {'radarr': False, 'sonarr': False, 'jellyfin': True}

        jellyfin_settings.JELLYFIN_API_KEY = ''

        assert jellyfin_api.get(ME_URL).data['integrations']['jellyfin'] is False

    def test_superuser_gets_flags_without_explicit_grant(self, api_client, user, arr_settings, jellyfin_settings):
        user.is_superuser = True
        user.save()
        api_client.force_authenticate(user=user)

        assert api_client.get(ME_URL).data['integrations'] == {'radarr': True, 'sonarr': True, 'jellyfin': True}
