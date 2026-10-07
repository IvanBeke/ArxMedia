from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from media.models import Movie, TVShow
from rest_framework.test import APIClient
from social.models import Follow
from tracking.models import WatchEntry

User = get_user_model()


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()

    def authenticate(self, user=None):
        if user is None:
            user = self.user
        self.client.force_authenticate(user=user)

    def test_register_user_logs_in(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'Newpass-123',
            'password2': 'Newpass-123'
        }
        response = self.client.post('/api/auth/register/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(response.data['username'], 'newuser')
        self.assertNotIn('password', response.data)
        self.assertEqual(self.client.get('/api/auth/me/').data['username'], 'newuser')

    def test_register_rejects_weak_password(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'weakuser',
            'email': 'weak@example.com',
            'password': '12345678',
            'password2': '12345678',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data)
        self.assertFalse(User.objects.filter(username='weakuser').exists())

    def test_login_starts_session(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        response = self.client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertIn('sessionid', response.cookies)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

    def test_login_rotates_session_key(self):
        self.client.get('/api/auth/me/')
        self.client.session.save()
        before = self.client.session.session_key
        self.client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        self.assertNotEqual(self.client.session.session_key, before)

    def test_logout_ends_session(self):
        self.client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_login_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        self.assertEqual(response.status_code, 403)

        client.get('/')
        token = client.cookies['csrftoken'].value
        response = client.post(
            '/api/auth/login/',
            {'username': 'testuser', 'password': 'testpass123'},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)

    def test_session_writes_require_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username='testuser', password='testpass123')
        response = client.patch('/api/auth/me/', {'bio': 'hi'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)

    def test_password_change_keeps_current_session(self):
        self.client.post('/api/auth/login/', {'username': 'testuser', 'password': 'testpass123'})
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'Fresh-pass-456',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

        other = APIClient()
        self.assertFalse(other.login(username='testuser', password='testpass123'))

    def test_login_unknown_user(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'missing-user',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn('Incorrect username or password.', str(response.data))

    def test_login_wrong_password(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn('Incorrect username or password.', str(response.data))

    def test_get_profile(self):
        self.authenticate()
        response = self.client.get(f'/api/auth/users/{self.user.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertIn('viewer_relationship', response.data)
        self.assertIn('permissions', response.data)
        self.assertIn('stats', response.data)
        self.assertIn('recent_activity', response.data)
        self.assertIn('visible_lists', response.data)

    def test_follow_user(self):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.authenticate()
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.following.filter(following=user2).exists())

    def test_unfollow_user(self):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.authenticate()
        # First follow
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.following.filter(following=user2).exists())
        # Then unfollow
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user.following.filter(following=user2).exists())

    def test_follow_self(self):
        self.authenticate()
        response = self.client.post(f'/api/auth/users/{self.user.username}/follow/')
        self.assertEqual(response.status_code, 400)

    def test_password_change_success(self):
        self.authenticate()
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('betterpass123'))
        self.assertFalse(self.user.check_password('testpass123'))

    def test_password_change_requires_auth(self):
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 401)

    def test_password_change_wrong_current_password(self):
        self.authenticate()
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'wrongpass',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 400)

    def test_update_preferred_region(self):
        self.authenticate()
        response = self.client.patch('/api/auth/me/', {
            'preferred_region': 'es'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['preferred_region'], 'ES')

        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_region, 'ES')

    def test_update_account_visibility(self):
        self.authenticate()
        response = self.client.patch('/api/auth/me/', {
            'account_visibility': 'friends_only'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['account_visibility'], 'friends_only')

        self.user.refresh_from_db()
        self.assertEqual(self.user.account_visibility, 'friends_only')

    def test_friends_only_profile_hidden_for_non_friend(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['permissions']['can_view_activity'])
        self.assertEqual(response.data['recent_activity'], [])
        self.assertEqual(response.data['visible_lists'], [])

    def test_friends_only_profile_visible_for_mutual_friend(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=self.user, following=target)
        Follow.objects.create(follower=target, following=self.user)
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['permissions']['can_view_activity'])
        self.assertTrue(response.data['viewer_relationship']['is_friend'])

    def test_followers_following_endpoints_respect_privacy(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        self.authenticate()

        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 403)
        self.assertEqual(following_response.status_code, 403)

        Follow.objects.create(follower=self.user, following=target)
        Follow.objects.create(follower=target, following=self.user)
        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 200)
        self.assertEqual(following_response.status_code, 200)

    def test_private_profile_hidden_for_anonymous_user(self):
        target = User.objects.create_user(
            username='private_target',
            email='private-target@example.com',
            password='pass123',
            account_visibility='private',
        )

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 401)

    def test_private_profile_visible_for_owner(self):
        self.user.account_visibility = 'private'
        self.user.save(update_fields=['account_visibility'])
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{self.user.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['permissions']['can_view_activity'])
        self.assertTrue(response.data['permissions']['can_view_lists'])
        self.assertTrue(response.data['viewer_relationship']['is_self'])

    def test_friends_only_profile_hidden_for_one_way_follow(self):
        target = User.objects.create_user(
            username='friends_target',
            email='friends-target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=self.user, following=target)
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['permissions']['can_view_activity'])
        self.assertFalse(response.data['viewer_relationship']['is_friend'])

    def test_public_followers_endpoint_returns_paginated_payload(self):
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

        self.authenticate()
        response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 20)

        page_two = self.client.get(f'/api/auth/users/{target.username}/followers/?page=2')
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(len(page_two.data['results']), 5)

    def test_private_followers_and_following_endpoints_forbidden(self):
        target = User.objects.create_user(
            username='private_graph_target',
            email='private-graph-target@example.com',
            password='pass123',
            account_visibility='private',
        )
        self.authenticate()

        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 403)
        self.assertEqual(following_response.status_code, 403)

    def test_profile_and_social_graph_endpoints_require_auth(self):
        target = User.objects.create_user(
            username='locked_target',
            email='locked-target@example.com',
            password='pass123',
            account_visibility='public',
        )

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f'/api/auth/users/{target.username}/').status_code, 401)
        self.assertEqual(self.client.get(f'/api/auth/users/{target.username}/followers/').status_code, 401)
        self.assertEqual(self.client.get(f'/api/auth/users/{target.username}/following/').status_code, 401)

    def test_user_search_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/auth/users/search/?q=test')
        self.assertEqual(response.status_code, 401)

    def test_user_search_requires_three_characters(self):
        User.objects.create_user(username='alice', email='alice@example.com', password='pass123')
        self.authenticate()

        response = self.client.get('/api/auth/users/search/?q=al')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_user_search_returns_matching_users_excluding_self(self):
        User.objects.create_user(username='alice_watcher', email='alice@example.com', password='pass123')
        User.objects.create_user(username='alice_runner', email='alice2@example.com', password='pass123')
        self.authenticate()

        response = self.client.get('/api/auth/users/search/?q=alice')
        self.assertEqual(response.status_code, 200)
        usernames = [row['username'] for row in response.data]
        self.assertEqual(usernames, ['alice_runner', 'alice_watcher'])
        self.assertNotIn(self.user.username, usernames)

    def _create_heatmap_media(self):
        Movie.objects.create(tmdb_id=101, title='Heatmap Movie', release_date=date(2020, 5, 1))
        TVShow.objects.create(tmdb_id=202, name='Heatmap Show')

    def test_activity_heatmap_returns_daily_counts(self):
        self._create_heatmap_media()
        other = User.objects.create_user(username='other', email='other@example.com', password='pass123')

        now = timezone.now()
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=101, watched_at=now - timedelta(days=2))
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=202, season_number=1, episode_number=1, watched_at=now - timedelta(days=2))
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=202, season_number=1, episode_number=2, watched_at=now)
        WatchEntry.objects.create(user=other, media_type='movie', tmdb_id=101, watched_at=now)

        self.authenticate()
        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 3)
        days = {day['date']: day for day in response.data['days']}

        today = timezone.localdate()
        two_days_ago = today - timedelta(days=2)

        self.assertEqual(days[two_days_ago.isoformat()]['count'], 2)
        items = days[two_days_ago.isoformat()]['items']
        self.assertEqual(len(items), 2)

        movie_item = next(item for item in items if item['media_type'] == 'movie')
        self.assertEqual(movie_item['title'], 'Heatmap Movie')
        self.assertEqual(movie_item['release_year'], 2020)
        self.assertEqual(movie_item['tmdb_id'], 101)

        episode_item = next(item for item in items if item['media_type'] == 'episode')
        self.assertEqual(episode_item['title'], 'Heatmap Show')
        self.assertEqual(episode_item['episode_code'], 'S01E01')
        self.assertEqual(episode_item['season_number'], 1)
        self.assertEqual(episode_item['episode_number'], 1)

        self.assertEqual(days[today.isoformat()]['count'], 1)
        self.assertEqual(days[today.isoformat()]['items'][0]['episode_code'], 'S01E02')

    def test_activity_heatmap_excludes_entries_outside_one_year_window(self):
        self._create_heatmap_media()
        Movie.objects.create(tmdb_id=102, title='Future Movie')
        Movie.objects.create(tmdb_id=103, title='Window Edge Movie')
        now = timezone.now()
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=101, watched_at=now - timedelta(days=400))
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=102, watched_at=now + timedelta(days=1))

        self.authenticate()
        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 0)
        self.assertTrue(all(day['count'] == 0 for day in response.data['days']))

        today = timezone.localdate()
        try:
            start = today.replace(year=today.year - 1)
        except ValueError:
            start = today.replace(year=today.year - 1, day=28)
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=103, watched_at=timezone.make_aware(datetime.combine(start, datetime.min.time())))

        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(len(response.data['days']), (today - start).days + 1)

    @patch('django.utils.timezone.localdate')
    def test_activity_heatmap_leap_year_window_includes_feb_29(self, mock_localdate):
        mock_localdate.return_value = date(2024, 3, 1)
        self._create_heatmap_media()
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=101,
            watched_at=timezone.make_aware(datetime.combine(date(2024, 2, 29), datetime.min.time())),
        )

        self.authenticate()
        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 1)
        # Mar 1 2023 through Mar 1 2024 inclusive (leap year).
        self.assertEqual(len(response.data['days']), 367)
        days = {day['date']: day for day in response.data['days']}
        self.assertEqual(days['2024-02-29']['count'], 1)

    def _heatmap_entry_sql(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')
        self.assertEqual(response.status_code, 200)
        return next(q['sql'] for q in ctx.captured_queries if 'tracking_watchentry' in q['sql'])

    def test_activity_heatmap_entry_query_has_no_per_row_subqueries(self):
        self.authenticate()
        Movie.objects.create(tmdb_id=5000, title='Movie')
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=5000, watched_at=timezone.now())

        self.assertEqual(self._heatmap_entry_sql().count('SELECT'), 1)

    def test_activity_heatmap_window_is_an_index_condition(self):
        self.authenticate()
        sql = self._heatmap_entry_sql()
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL enable_seqscan = off')
            cursor.execute('SET LOCAL enable_bitmapscan = off')
            cursor.execute('EXPLAIN ' + sql)
            plan = '\n'.join(row[0] for row in cursor.fetchall())

        index_cond = next(line for line in plan.splitlines() if 'Index Cond' in line)
        self.assertIn('watchentry_user_history_idx', plan)
        self.assertIn('watched_at', index_cond)

    def test_activity_heatmap_hidden_from_stranger_on_private_profile(self):
        target = User.objects.create_user(
            username='private_heatmap',
            email='private-heatmap@example.com',
            password='pass123',
            account_visibility='private',
        )
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/activity/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'days': [], 'total': 0})

    def test_activity_heatmap_visible_to_mutual_friend(self):
        target = User.objects.create_user(
            username='friends_heatmap',
            email='friends-heatmap@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=self.user, following=target)
        Follow.objects.create(follower=target, following=self.user)
        self._create_heatmap_media()
        WatchEntry.objects.create(
            user=target,
            media_type='episode',
            tmdb_id=202,
            season_number=2,
            episode_number=5,
            watched_at=timezone.now(),
        )
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/activity/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 1)
        today = timezone.localdate()
        items = {day['date']: day['items'] for day in response.data['days']}[today.isoformat()]
        self.assertEqual(items[0]['episode_code'], 'S02E05')

    def test_activity_heatmap_requires_auth(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')
        self.assertEqual(response.status_code, 401)
