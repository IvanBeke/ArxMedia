import pytest

from social.models import Follow

pytestmark = pytest.mark.django_db

SECTIONS = ['ratings', 'library', 'watch-count', 'watch-time', 'monthly', 'years', 'habits']


@pytest.mark.parametrize('section', SECTIONS)
class StatsAccessTests:
    def test_requires_auth(self, section, user, api_client):
        assert api_client.get(f'/api/stats/{user.username}/{section}/').status_code == 401

    def test_unknown_user_is_not_found(self, section, user, auth_client):
        assert auth_client.get(f'/api/stats/nobody/{section}/').status_code == 404

    def test_another_public_user_is_visible(self, section, user, auth_client, user2, tmdb_noop):
        assert auth_client.get(f'/api/stats/{user2.username}/{section}/').status_code == 200

    def test_private_profile_is_forbidden_for_a_stranger(self, section, user, auth_client, user2, tmdb_noop):
        user2.account_visibility = 'private'
        user2.save(update_fields=['account_visibility'])

        assert auth_client.get(f'/api/stats/{user2.username}/{section}/').status_code == 403

    def test_private_profile_is_visible_to_its_owner(self, section, user, auth_client, tmdb_noop):
        user.account_visibility = 'private'
        user.save(update_fields=['account_visibility'])

        assert auth_client.get(f'/api/stats/{user.username}/{section}/').status_code == 200

    def test_friends_only_profile_needs_a_mutual_follow(self, section, user, auth_client, user2, tmdb_noop):
        user2.account_visibility = 'friends_only'
        user2.save(update_fields=['account_visibility'])
        url = f'/api/stats/{user2.username}/{section}/'

        assert auth_client.get(url).status_code == 403

        Follow.objects.create(follower=user, following=user2)
        assert auth_client.get(url).status_code == 403

        Follow.objects.create(follower=user2, following=user)
        assert auth_client.get(url).status_code == 200
