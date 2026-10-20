from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from media.models import Movie, TVShow
from social.models import Follow
from tracking.models import WatchEntry

User = get_user_model()


pytestmark = pytest.mark.django_db

class AccountTests:
    def test_register_user_logs_in(self, user, api_client):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'Newpass-123',
            'password2': 'Newpass-123'
        }
        response = api_client.post('/api/auth/register/', data)
        assert response.status_code == 201
        assert User.objects.count() == 2
        assert response.data['username'] == 'newuser'
        assert 'password' not in response.data
        assert api_client.get('/api/auth/me/').data['username'] == 'newuser'

    def test_register_rejects_weak_password(self, user, api_client):
        response = api_client.post('/api/auth/register/', {
            'username': 'weakuser',
            'email': 'weak@example.com',
            'password': '12345678',
            'password2': '12345678',
        })
        assert response.status_code == 400
        assert 'password' in response.data
        assert not User.objects.filter(username='weakuser').exists()

    def test_login_starts_session(self, user, api_client):
        assert api_client.get('/api/auth/me/').status_code == 401
        response = api_client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        assert response.status_code == 200
        assert response.data['username'] == 'testuser'
        assert 'sessionid' in response.cookies
        assert api_client.get('/api/auth/me/').status_code == 200

    def test_login_rotates_session_key(self, user, api_client):
        api_client.get('/api/auth/me/')
        api_client.session.save()
        before = api_client.session.session_key
        api_client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        assert api_client.session.session_key != before

    def test_logout_ends_session(self, user, api_client):
        api_client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        response = api_client.post('/api/auth/logout/')
        assert response.status_code == 204
        assert api_client.get('/api/auth/me/').status_code == 401

    def test_login_requires_csrf_token(self, user):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        assert response.status_code == 403

        with patch(
            'django_vite.templatetags.django_vite.DjangoViteAssetLoader.instance'
        ) as loader_instance:
            loader_instance.return_value.generate_vite_asset.return_value = ''
            client.get('/')
        token = client.cookies['csrftoken'].value
        response = client.post(
            '/api/auth/login/',
            {'username': 'testuser', 'password': 'testpass123'},
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 200

    def test_session_writes_require_csrf_token(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='testpass123')
        response = client.patch('/api/auth/me/', {'bio': 'hi'}, format='json')
        assert response.status_code == 403
        assert client.get('/api/auth/me/').status_code == 200

    def test_password_change_keeps_current_session(self, user, api_client):
        api_client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        response = api_client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'Fresh-pass-456',
        })
        assert response.status_code == 200
        assert api_client.get('/api/auth/me/').status_code == 200

        other = APIClient()
        assert not other.login(username='testuser', password='testpass123')

    def test_login_unknown_user(self, user, api_client):
        response = api_client.post('/api/auth/login/', {
            'username': 'missing-user',
            'password': 'testpass123',
        })
        assert response.status_code == 401
        assert 'Incorrect username or password.' in str(response.data)

    def test_login_wrong_password(self, user, api_client):
        response = api_client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrong-password',
        })
        assert response.status_code == 401
        assert 'Incorrect username or password.' in str(response.data)

    def test_me_exposes_staff_flag(self, user, auth_client):
        response = auth_client.get('/api/auth/me/')
        assert response.status_code == 200
        assert response.data['is_staff'] is False

        user.is_staff = True
        user.save(update_fields=['is_staff'])

        response = auth_client.get('/api/auth/me/')
        assert response.data['is_staff'] is True

    def test_me_cannot_update_staff_flag(self, user, auth_client):
        response = auth_client.patch('/api/auth/me/', {'is_staff': True}, format='json')

        assert response.status_code == 200
        assert response.data['is_staff'] is False
        user.refresh_from_db()
        assert user.is_staff is False

    def test_get_profile(self, user, auth_client):
        response = auth_client.get(f'/api/auth/users/{user.username}/')
        assert response.status_code == 200
        assert response.data['username'] == 'testuser'
        assert 'viewer_relationship' in response.data
        assert 'permissions' in response.data
        assert 'stats' in response.data
        assert 'recent_activity' in response.data
        assert 'visible_lists' in response.data

    def test_follow_user(self, user, auth_client):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        response = auth_client.post(f'/api/auth/users/{user2.username}/follow/')
        assert response.status_code == 200
        assert user.following.filter(following=user2).exists()

    def test_unfollow_user(self, user, auth_client):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        # First follow
        response = auth_client.post(f'/api/auth/users/{user2.username}/follow/')
        assert response.status_code == 200
        assert user.following.filter(following=user2).exists()
        # Then unfollow
        response = auth_client.post(f'/api/auth/users/{user2.username}/follow/')
        assert response.status_code == 200
        assert not user.following.filter(following=user2).exists()

    def test_follow_self(self, user, auth_client):
        response = auth_client.post(f'/api/auth/users/{user.username}/follow/')
        assert response.status_code == 400

    def test_password_change_success(self, user, auth_client):
        response = auth_client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        assert response.status_code == 200

        user.refresh_from_db()
        assert user.check_password('betterpass123')
        assert not user.check_password('testpass123')

    def test_password_change_requires_auth(self, user, api_client):
        response = api_client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        assert response.status_code == 401

    def test_password_change_wrong_current_password(self, user, auth_client):
        response = auth_client.post('/api/auth/password/change/', {
            'current_password': 'wrongpass',
            'new_password': 'betterpass123'
        })
        assert response.status_code == 400

    def test_update_preferred_region(self, user, auth_client):
        response = auth_client.patch('/api/auth/me/', {
            'preferred_region': 'es'
        }, format='json')
        assert response.status_code == 200
        assert response.data['preferred_region'] == 'ES'

        user.refresh_from_db()
        assert user.preferred_region == 'ES'

    def test_update_account_visibility(self, user, auth_client):
        response = auth_client.patch('/api/auth/me/', {
            'account_visibility': 'friends_only'
        }, format='json')
        assert response.status_code == 200
        assert response.data['account_visibility'] == 'friends_only'

        user.refresh_from_db()
        assert user.account_visibility == 'friends_only'

    def test_friends_only_profile_hidden_for_non_friend(self, user, auth_client):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )

        response = auth_client.get(f'/api/auth/users/{target.username}/')
        assert response.status_code == 200
        assert not response.data['permissions']['can_view_activity']
        assert response.data['recent_activity'] == []
        assert response.data['visible_lists'] == []

    def test_friends_only_profile_visible_for_mutual_friend(self, user, auth_client):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=user, following=target)
        Follow.objects.create(follower=target, following=user)

        response = auth_client.get(f'/api/auth/users/{target.username}/')
        assert response.status_code == 200
        assert response.data['permissions']['can_view_activity']
        assert response.data['viewer_relationship']['is_friend']

    def test_followers_following_endpoints_respect_privacy(self, user, auth_client):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )

        followers_response = auth_client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = auth_client.get(f'/api/auth/users/{target.username}/following/')
        assert followers_response.status_code == 403
        assert following_response.status_code == 403

        Follow.objects.create(follower=user, following=target)
        Follow.objects.create(follower=target, following=user)
        followers_response = auth_client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = auth_client.get(f'/api/auth/users/{target.username}/following/')
        assert followers_response.status_code == 200
        assert following_response.status_code == 200

    def test_private_profile_hidden_for_anonymous_user(self, user, api_client):
        target = User.objects.create_user(
            username='private_target',
            email='private-target@example.com',
            password='pass123',
            account_visibility='private',
        )

        response = api_client.get(f'/api/auth/users/{target.username}/')
        assert response.status_code == 401

    def test_private_profile_visible_for_owner(self, user, auth_client):
        user.account_visibility = 'private'
        user.save(update_fields=['account_visibility'])

        response = auth_client.get(f'/api/auth/users/{user.username}/')
        assert response.status_code == 200
        assert response.data['permissions']['can_view_activity']
        assert response.data['permissions']['can_view_lists']
        assert response.data['viewer_relationship']['is_self']

    def test_friends_only_profile_hidden_for_one_way_follow(self, user, auth_client):
        target = User.objects.create_user(
            username='friends_target',
            email='friends-target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=user, following=target)

        response = auth_client.get(f'/api/auth/users/{target.username}/')
        assert response.status_code == 200
        assert not response.data['permissions']['can_view_activity']
        assert not response.data['viewer_relationship']['is_friend']

    def test_public_followers_endpoint_returns_paginated_payload(self, user, auth_client):
        target = User.objects.create_user(
            username='public_target',
            email='public-target@example.com',
            password='pass123',
            account_visibility='public',
        )

        for index in range(25):
            follower = User.objects.create_user(
                username=f'follower_{index}',
                email=f'follower_{index}@example.com',
                password='pass123',
            )
            Follow.objects.create(follower=follower, following=target)

        response = auth_client.get(f'/api/auth/users/{target.username}/followers/')
        assert response.status_code == 200
        assert response.data['count'] == 25
        assert len(response.data['results']) == 20

        page_two = auth_client.get(f'/api/auth/users/{target.username}/followers/?page=2')
        assert page_two.status_code == 200
        assert len(page_two.data['results']) == 5

    def test_private_followers_and_following_endpoints_forbidden(self, user, auth_client):
        target = User.objects.create_user(
            username='private_graph_target',
            email='private-graph-target@example.com',
            password='pass123',
            account_visibility='private',
        )

        followers_response = auth_client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = auth_client.get(f'/api/auth/users/{target.username}/following/')
        assert followers_response.status_code == 403
        assert following_response.status_code == 403

    def test_profile_and_social_graph_endpoints_require_auth(self, user, api_client):
        target = User.objects.create_user(
            username='locked_target',
            email='locked-target@example.com',
            password='pass123',
            account_visibility='public',
        )

        assert api_client.get(f'/api/auth/users/{target.username}/').status_code == 401
        assert api_client.get(f'/api/auth/users/{target.username}/followers/').status_code == 401
        assert api_client.get(f'/api/auth/users/{target.username}/following/').status_code == 401

    def test_user_search_requires_auth(self, user, api_client):
        response = api_client.get('/api/auth/users/search/?q=test')
        assert response.status_code == 401

    def test_user_search_requires_three_characters(self, user, auth_client):
        User.objects.create_user(username='alice', email='alice@example.com', password='pass123')

        response = auth_client.get('/api/auth/users/search/?q=al')
        assert response.status_code == 200
        assert response.data == []

    def test_user_search_returns_matching_users_excluding_self(self, user, auth_client):
        User.objects.create_user(username='alice_watcher', email='alice@example.com', password='pass123')
        User.objects.create_user(username='alice_runner', email='alice2@example.com', password='pass123')

        response = auth_client.get('/api/auth/users/search/?q=alice')
        assert response.status_code == 200
        usernames = [row['username'] for row in response.data]
        assert usernames == ['alice_runner', 'alice_watcher']
        assert user.username not in usernames

    def _create_heatmap_media(self):
        Movie.objects.create(tmdb_id=101, title='Heatmap Movie', release_date=date(2020, 5, 1))
        TVShow.objects.create(tmdb_id=202, name='Heatmap Show')

    def test_activity_heatmap_returns_daily_counts(self, user, auth_client):
        self._create_heatmap_media()
        other = User.objects.create_user(username='other', email='other@example.com', password='pass123')

        now = timezone.now()
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=101, watched_at=now - timedelta(days=2))
        WatchEntry.objects.create(user=user, media_type='episode', tmdb_id=202, season_number=1, episode_number=1, watched_at=now - timedelta(days=2))
        WatchEntry.objects.create(user=user, media_type='episode', tmdb_id=202, season_number=1, episode_number=2, watched_at=now)
        WatchEntry.objects.create(user=other, media_type='movie', tmdb_id=101, watched_at=now)

        response = auth_client.get(f'/api/auth/users/{user.username}/activity/')

        assert response.status_code == 200
        assert response.data['total'] == 3
        days = {day['date']: day for day in response.data['days']}

        today = timezone.localdate()
        two_days_ago = today - timedelta(days=2)

        assert days[two_days_ago.isoformat()]['count'] == 2
        items = days[two_days_ago.isoformat()]['items']
        assert len(items) == 2

        movie_item = next(item for item in items if item['media_type'] == 'movie')
        assert movie_item['title'] == 'Heatmap Movie'
        assert movie_item['release_year'] == 2020
        assert movie_item['tmdb_id'] == 101

        episode_item = next(item for item in items if item['media_type'] == 'episode')
        assert episode_item['title'] == 'Heatmap Show'
        assert episode_item['episode_code'] == 'S01E01'
        assert episode_item['season_number'] == 1
        assert episode_item['episode_number'] == 1

        assert days[today.isoformat()]['count'] == 1
        assert days[today.isoformat()]['items'][0]['episode_code'] == 'S01E02'

    def test_activity_heatmap_excludes_entries_outside_one_year_window(self, user, auth_client):
        self._create_heatmap_media()
        Movie.objects.create(tmdb_id=102, title='Future Movie')
        Movie.objects.create(tmdb_id=103, title='Window Edge Movie')
        now = timezone.now()
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=101, watched_at=now - timedelta(days=400))
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=102, watched_at=now + timedelta(days=1))

        response = auth_client.get(f'/api/auth/users/{user.username}/activity/')

        assert response.status_code == 200
        assert response.data['total'] == 0
        assert all(day['count'] == 0 for day in response.data['days'])

        today = timezone.localdate()
        try:
            start = today.replace(year=today.year - 1)
        except ValueError:
            start = today.replace(year=today.year - 1, day=28)
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=103, watched_at=timezone.make_aware(datetime.combine(start, datetime.min.time())))

        response = auth_client.get(f'/api/auth/users/{user.username}/activity/')
        assert response.data['total'] == 1
        assert len(response.data['days']) == (today - start).days + 1

    def test_activity_heatmap_leap_year_window_includes_feb_29(self, mocker, user, auth_client):
        mock_localdate = mocker.patch('django.utils.timezone.localdate')
        mock_localdate.return_value = date(2024, 3, 1)
        self._create_heatmap_media()
        WatchEntry.objects.create(
            user=user,
            media_type='movie',
            tmdb_id=101,
            watched_at=timezone.make_aware(datetime.combine(date(2024, 2, 29), datetime.min.time())),
        )

        response = auth_client.get(f'/api/auth/users/{user.username}/activity/')

        assert response.status_code == 200
        assert response.data['total'] == 1
        # Mar 1 2023 through Mar 1 2024 inclusive (leap year).
        assert len(response.data['days']) == 367
        days = {day['date']: day for day in response.data['days']}
        assert days['2024-02-29']['count'] == 1

    def _heatmap_entry_sql(self, client, username):
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(f'/api/auth/users/{username}/activity/')
        assert response.status_code == 200
        return next(q['sql'] for q in ctx.captured_queries if 'tracking_watchentry' in q['sql'])

    def test_activity_heatmap_entry_query_has_no_per_row_subqueries(self, user, auth_client):
        Movie.objects.create(tmdb_id=5000, title='Movie')
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=5000, watched_at=timezone.now())

        assert self._heatmap_entry_sql(auth_client, user.username).count('SELECT') == 1

    def test_activity_heatmap_window_is_an_index_condition(self, user, auth_client):
        sql = self._heatmap_entry_sql(auth_client, user.username)
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL enable_seqscan = off')
            cursor.execute('SET LOCAL enable_bitmapscan = off')
            cursor.execute('EXPLAIN ' + sql)
            plan = '\n'.join(row[0] for row in cursor.fetchall())

        index_cond = next(line for line in plan.splitlines() if 'Index Cond' in line)
        assert 'watchentry_user_history_idx' in plan
        assert 'watched_at' in index_cond

    def test_activity_heatmap_hidden_from_stranger_on_private_profile(self, user, auth_client):
        target = User.objects.create_user(
            username='private_heatmap',
            email='private-heatmap@example.com',
            password='pass123',
            account_visibility='private',
        )

        response = auth_client.get(f'/api/auth/users/{target.username}/activity/')
        assert response.status_code == 200
        assert response.data == {'days': [], 'total': 0}

    def test_activity_heatmap_visible_to_mutual_friend(self, user, auth_client):
        target = User.objects.create_user(
            username='friends_heatmap',
            email='friends-heatmap@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=user, following=target)
        Follow.objects.create(follower=target, following=user)
        self._create_heatmap_media()
        WatchEntry.objects.create(
            user=target,
            media_type='episode',
            tmdb_id=202,
            season_number=2,
            episode_number=5,
            watched_at=timezone.now(),
        )

        response = auth_client.get(f'/api/auth/users/{target.username}/activity/')
        assert response.status_code == 200
        assert response.data['total'] == 1
        today = timezone.localdate()
        items = {day['date']: day['items'] for day in response.data['days']}[today.isoformat()]
        assert items[0]['episode_code'] == 'S02E05'

    def test_activity_heatmap_requires_auth(self, user, api_client):
        response = api_client.get(f'/api/auth/users/{user.username}/activity/')
        assert response.status_code == 401
