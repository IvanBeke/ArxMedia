import pytest
from django.urls import reverse

ME_URL = reverse('me')


@pytest.mark.django_db
class TestMeIntegrationFlags:
    def test_all_flags_are_false_without_permission(self, auth_client, arr_settings):
        assert auth_client.get(ME_URL).data['integrations'] == {'radarr': False, 'sonarr': False, 'jellyfin': False}

    def test_radarr_flag_requires_configuration(self, api_client, arr_user, settings):
        settings.RADARR_URL = ''
        settings.RADARR_API_KEY = ''
        api_client.force_authenticate(user=arr_user)

        assert api_client.get(ME_URL).data['integrations']['radarr'] is False

    def test_radarr_flag_is_true_with_permission_and_configuration(self, arr_client):
        assert arr_client.get(ME_URL).data['integrations']['radarr'] is True

    def test_superuser_gets_flag_without_explicit_grant(self, api_client, user, arr_settings):
        user.is_superuser = True
        user.save()
        api_client.force_authenticate(user=user)

        assert api_client.get(ME_URL).data['integrations']['radarr'] is True
