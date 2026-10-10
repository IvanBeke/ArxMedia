from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from media.models import Episode, Genre, Movie, Season, TVShow
from tracking.models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)
from tracking.status_sync import refresh_show_status

User = get_user_model()
from .base import BaseTestCase


class UpNextTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Create a test show in the database
        from media.models import Episode, Season, TVShow
        self.show = TVShow.objects.create(
            tmdb_id=123,
            name='Test Show',
            poster_path='/test.jpg',
            first_air_date='2024-01-01'
        )
        self.season1 = Season.objects.create(
            show=self.show,
            season_number=1,
            tmdb_id=1234
        )
        # Create episodes for season 1
        for i in range(1, 11):
            Episode.objects.create(
                season=self.season1,
                tmdb_id=2000 + i,  # Unique TMDB ID for each episode
                episode_number=i,
                name=f'Episode {i}',
                air_date='2024-01-01',
                runtime=24,
            )
        # Create season 2
        self.season2 = Season.objects.create(
            show=self.show,
            season_number=2,
            tmdb_id=1235
        )
        Episode.objects.create(
            season=self.season2,
            tmdb_id=2011,
            episode_number=1,
            name='S2 Episode 1',
            air_date='2024-02-01',
            runtime=24,
        )

    def test_up_next_empty(self):
        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_up_next_with_progress(self):
        # Mark S1E1,2,3 as watched (episodes already exist from setUp)
        for i in range(1, 4):
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=123,
                season_number=1, episode_number=i
            )
        
        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Should return S1E4 as next episode
        self.assertEqual(response.data[0]['next_episode']['season_number'], 1)
        self.assertEqual(response.data[0]['next_episode']['episode_number'], 4)

    def test_up_next_uses_current_watch_entries_when_status_pointer_would_be_stale(self):
        for episode_number in range(1, 5):
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=123,
                season_number=1, episode_number=episode_number,
            )

        response = self.client.get('/api/tracking/up-next/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['next_episode']['episode_number'], 5)

    def test_up_next_uses_broadcast_timestamp_over_date_only_ordering(self):
        show = TVShow.objects.create(tmdb_id=778, name='Timestamp Show')
        season = Season.objects.create(show=show, tmdb_id=7781, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=77811,
            episode_number=1,
            name='Later Broadcast',
            air_date='2026-01-01',
            broadcast_start=timezone.make_aware(timezone.datetime(2026, 1, 1, 23, 0)),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=77812,
            episode_number=2,
            name='Earlier Broadcast',
            air_date='2026-01-01',
            broadcast_start=timezone.make_aware(timezone.datetime(2026, 1, 1, 1, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=778,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')

        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data if entry['tmdb_id'] == 778)
        self.assertEqual(item['next_episode']['episode_number'], 2)

    def test_up_next_isolated_between_users(self):
        show = TVShow.objects.create(tmdb_id=779, name='Shared Progress Show')
        season = Season.objects.create(show=show, tmdb_id=7791, season_number=1, name='Season 1')
        for episode_number in (1, 2, 3):
            Episode.objects.create(
                season=season,
                tmdb_id=77900 + episode_number,
                episode_number=episode_number,
                name=f'Episode {episode_number}',
                air_date=timezone.localdate() - timedelta(days=1),
            )
        for user, episode_number in ((self.user, 1), (self.user2, 2)):
            WatchEntry.objects.create(
                user=user,
                media_type='episode',
                tmdb_id=779,
                season_number=1,
                episode_number=episode_number,
            )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(next(item for item in response.data if item['tmdb_id'] == 779)['next_episode']['episode_number'], 2)

        self.authenticate(self.user2)
        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(next(item for item in response.data if item['tmdb_id'] == 779)['next_episode']['episode_number'], 1)

    def test_up_next_uses_broadcast_start_for_release_boundary(self):
        show = TVShow.objects.create(tmdb_id=780, name='Broadcast Boundary Show')
        season = Season.objects.create(show=show, tmdb_id=7801, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=78001,
            episode_number=1,
            name='Future Broadcast',
            air_date=timezone.localdate() - timedelta(days=1),
            broadcast_start=timezone.now() + timedelta(hours=1),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=780,
            season_number=1,
            episode_number=1,
        )

        self.assertTrue(UserMediaStatus.objects.for_user(self.user).shows().progressable().filter(tmdb_id=780).exists())
        annotated = UserMediaStatus.objects.for_user(self.user).shows().with_next_episode().filter(tmdb_id=780).first()
        self.assertIsNone(annotated.next_episode_id)

    def test_orphan_watch_key_does_not_qualify_as_progressable(self):
        show = TVShow.objects.create(tmdb_id=782, name='Orphan History Show')
        season = Season.objects.create(show=show, tmdb_id=7821, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=78201,
            episode_number=1,
            name='Only Episode',
            air_date=timezone.localdate() - timedelta(days=1),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=782,
            season_number=1,
            episode_number=99,
        )

        self.assertFalse(UserMediaStatus.objects.for_user(self.user).shows().progressable().filter(tmdb_id=782).exists())

    def test_up_next_falls_back_to_air_date_without_broadcast_start(self):
        show = TVShow.objects.create(tmdb_id=781, name='Dateless Broadcast Show')
        season = Season.objects.create(show=show, tmdb_id=7811, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=78101,
            episode_number=1,
            name='Aired Without Timestamp',
            air_date=timezone.localdate() - timedelta(days=2),
            broadcast_start=None,
        )
        Episode.objects.create(
            season=season,
            tmdb_id=78102,
            episode_number=2,
            name='Second Aired',
            air_date=timezone.localdate() - timedelta(days=1),
            broadcast_start=None,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=781,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(next(item for item in response.data if item['tmdb_id'] == 781)['next_episode']['episode_number'], 2)

    def test_up_next_includes_progress_and_remaining_runtime_fields(self):
        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=777, name='Runtime Show')
        season = Season.objects.create(show=show, tmdb_id=7771, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=77711, episode_number=1, name='Episode 1', air_date=today - timedelta(days=5), runtime=20)
        Episode.objects.create(
            season=season,
            tmdb_id=77712,
            episode_number=2,
            name='Episode 2',
            air_date=today - timedelta(days=4),
            runtime=30,
            episode_type='season finale',
        )
        Episode.objects.create(season=season, tmdb_id=77713, episode_number=3, name='Episode 3', air_date=today - timedelta(days=2), runtime=None)
        Episode.objects.create(season=season, tmdb_id=77714, episode_number=4, name='Episode 4', air_date=today + timedelta(days=2), runtime=45)

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=777,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data if entry['tmdb_id'] == 777)

        self.assertEqual(item['next_episode']['episode_number'], 2)
        self.assertEqual(item['next_episode']['runtime'], 30)
        self.assertEqual(item['next_episode']['episode_type'], 'season finale')
        self.assertEqual(item['episodes_left'], 2)
        self.assertEqual(item['runtime_left_minutes'], 30)
        self.assertEqual(item['runtime_left_has_unknown'], True)
        self.assertEqual(item['progress_percent'], 33)

    def test_up_next_season_boundary(self):
        # Create season 1 and 2 with episodes
        show = TVShow.objects.create(tmdb_id=456, name='Test Show 2')
        season1 = Season.objects.create(show=show, tmdb_id=4561, season_number=1, name='Season 1')
        season2 = Season.objects.create(show=show, tmdb_id=4562, season_number=2, name='Season 2')
        for i in range(1, 11):
            Episode.objects.create(season=season1, tmdb_id=45610+i, episode_number=i, name=f'Episode {i}', air_date='2024-01-01')
        Episode.objects.create(season=season2, tmdb_id=45621, episode_number=1, name='Episode 1', air_date='2024-02-01')
        # Mark S1E1-10 as watched
        for i in range(1, 11):
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=456,
                season_number=1, episode_number=i
            )
        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Should return S2E1 as next episode
        self.assertEqual(response.data[0]['next_episode']['season_number'], 2)
        self.assertEqual(response.data[0]['next_episode']['episode_number'], 1)

    def test_up_next_orders_by_most_recent_watch(self):
        from media.models import Episode, Season, TVShow

        show2 = TVShow.objects.create(tmdb_id=999, name='Another Show')
        season2 = Season.objects.create(show=show2, tmdb_id=9991, season_number=1, name='Season 1')
        Episode.objects.create(season=season2, tmdb_id=99911, episode_number=1, name='Episode 1', air_date='2024-01-01')
        Episode.objects.create(season=season2, tmdb_id=99912, episode_number=2, name='Episode 2', air_date='2024-01-08')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=123,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 1, 0, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=999,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 2, 0, 0, 0)),
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['tmdb_id'], 999)
        self.assertEqual(response.data[1]['tmdb_id'], 123)

    def test_up_next_prioritizes_recent_releases_with_new_badge(self):
        from media.models import Episode, Season, TVShow

        today = timezone.now().date()

        show_newer = TVShow.objects.create(tmdb_id=1001, name='Newer Show')
        season_newer = Season.objects.create(show=show_newer, tmdb_id=10011, season_number=1, name='Season 1')
        Episode.objects.create(season=season_newer, tmdb_id=100111, episode_number=1, name='Episode 1', air_date=today - timedelta(days=2))
        Episode.objects.create(season=season_newer, tmdb_id=100112, episode_number=2, name='Episode 2', air_date=today - timedelta(days=1))

        show_older_new = TVShow.objects.create(tmdb_id=1002, name='Older New Show')
        season_older_new = Season.objects.create(show=show_older_new, tmdb_id=10021, season_number=1, name='Season 1')
        Episode.objects.create(season=season_older_new, tmdb_id=100211, episode_number=1, name='Episode 1', air_date=today - timedelta(days=5))
        Episode.objects.create(season=season_older_new, tmdb_id=100212, episode_number=2, name='Episode 2', air_date=today - timedelta(days=3))

        show_old = TVShow.objects.create(tmdb_id=1003, name='Old Show')
        season_old = Season.objects.create(show=show_old, tmdb_id=10031, season_number=1, name='Season 1')
        Episode.objects.create(season=season_old, tmdb_id=100311, episode_number=1, name='Episode 1', air_date=today - timedelta(days=30))
        Episode.objects.create(season=season_old, tmdb_id=100312, episode_number=2, name='Episode 2', air_date=today - timedelta(days=20))

        watched_time = timezone.make_aware(timezone.datetime(2026, 1, 3, 0, 0, 0))
        for show_id in (1001, 1002, 1003):
            WatchEntry.objects.create(
                user=self.user,
                media_type='episode',
                tmdb_id=show_id,
                season_number=1,
                episode_number=1,
                watched_at=watched_time,
            )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        self.assertEqual(response.data[0]['tmdb_id'], 1001)
        self.assertEqual(response.data[1]['tmdb_id'], 1002)
        self.assertEqual(response.data[2]['tmdb_id'], 1003)

        self.assertEqual(response.data[0]['is_new'], True)
        self.assertEqual(response.data[1]['is_new'], True)
        self.assertEqual(response.data[2]['is_new'], False)

    def test_up_next_ignores_dropped_shows(self):
        from media.models import Episode, Season, TVShow

        show_dropped = TVShow.objects.create(tmdb_id=2001, name='Dropped Show')
        season_dropped = Season.objects.create(show=show_dropped, tmdb_id=20011, season_number=1, name='Season 1')
        Episode.objects.create(season=season_dropped, tmdb_id=200111, episode_number=1, name='Episode 1', air_date='2024-01-01')
        Episode.objects.create(season=season_dropped, tmdb_id=200112, episode_number=2, name='Episode 2', air_date='2024-01-08')

        show_kept = TVShow.objects.create(tmdb_id=2002, name='Kept Show')
        season_kept = Season.objects.create(show=show_kept, tmdb_id=20021, season_number=1, name='Season 1')
        Episode.objects.create(season=season_kept, tmdb_id=200211, episode_number=1, name='Episode 1', air_date='2024-01-01')
        Episode.objects.create(season=season_kept, tmdb_id=200212, episode_number=2, name='Episode 2', air_date='2024-01-08')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2001,
            season_number=1,
            episode_number=1,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2002,
            season_number=1,
            episode_number=1,
        )
        UserMediaStatus.objects.update_or_create(
            user=self.user,
            media_type='tv',
            tmdb_id=2001,
            defaults={
                'status': 'dropped',
                'watched_episodes': 1,
                'total_episodes': 2,
                'progress_percent': 50,
                'dropped_at': timezone.now(),
                'status_changed_at': timezone.now(),
            },
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['tmdb_id'], 2002)

    def test_upcoming_empty(self):
        response = self.client.get('/api/tracking/upcoming/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_upcoming_returns_every_episode_in_seven_day_window(self):
        today = timezone.localdate()
        show = TVShow.objects.create(tmdb_id=3101, name='Weekly Show')
        season = Season.objects.create(show=show, tmdb_id=31011, season_number=1, name='Season 1')
        watched = Episode.objects.create(
            season=season,
            tmdb_id=310110,
            episode_number=1,
            name='Watched Episode',
            air_date=today - timedelta(days=1),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=310111,
            episode_number=2,
            name='Today Episode',
            air_date=today,
        )
        Episode.objects.create(
            season=season,
            tmdb_id=310112,
            episode_number=3,
            name='Later This Week',
            air_date=today + timedelta(days=3),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=310113,
            episode_number=4,
            name='Outside Window',
            air_date=today + timedelta(days=7),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=show.tmdb_id,
            season_number=season.season_number,
            episode_number=watched.episode_number,
        )

        response = self.client.get('/api/tracking/upcoming/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(item['season_number'], item['episode_number']) for item in response.data],
            [(1, 2), (1, 3)],
        )

    @override_settings(TIME_ZONE='America/New_York')
    def test_upcoming_date_window_uses_configured_timezone(self):
        today = timezone.localdate()
        show = TVShow.objects.create(tmdb_id=3151, name='Timezone Weekly Show')
        season = Season.objects.create(show=show, tmdb_id=31511, season_number=1, name='Season 1')
        watched = Episode.objects.create(
            season=season,
            tmdb_id=315110,
            episode_number=1,
            name='Watched Episode',
            air_date=today - timedelta(days=1),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=315111,
            episode_number=2,
            name='Today Episode',
            air_date=today,
        )
        Episode.objects.create(
            season=season,
            tmdb_id=315112,
            episode_number=3,
            name='Outside Window',
            air_date=today + timedelta(days=7),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=show.tmdb_id,
            season_number=season.season_number,
            episode_number=watched.episode_number,
        )

        response = self.client.get('/api/tracking/upcoming/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['name'] for item in response.data], ['Today Episode'])

    def test_upcoming_is_not_limited_to_five_shows(self):
        today = timezone.localdate()
        for index in range(6):
            show = TVShow.objects.create(tmdb_id=3200 + index, name=f'Weekly Show {index + 1}')
            season = Season.objects.create(
                show=show,
                tmdb_id=(3200 + index) * 10,
                season_number=1,
                name='Season 1',
            )
            watched = Episode.objects.create(
                season=season,
                tmdb_id=(3200 + index) * 100 + 1,
                episode_number=1,
                name='Watched Episode',
                air_date=today - timedelta(days=1),
            )
            Episode.objects.create(
                season=season,
                tmdb_id=(3200 + index) * 100 + 2,
                episode_number=2,
                name='Upcoming Episode',
                air_date=today + timedelta(days=index + 1),
            )
            WatchEntry.objects.create(
                user=self.user,
                media_type='episode',
                tmdb_id=show.tmdb_id,
                season_number=season.season_number,
                episode_number=watched.episode_number,
            )

        response = self.client.get('/api/tracking/upcoming/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 6)
        self.assertEqual(
            [item['tmdb_id'] for item in response.data],
            [3200, 3201, 3202, 3203, 3204, 3205],
        )

    def test_upcoming_filters_and_orders_episodes_by_broadcast_timestamp(self):
        today = timezone.localdate()
        show = TVShow.objects.create(tmdb_id=3301, name='Broadcast Order Show')
        season = Season.objects.create(show=show, tmdb_id=33011, season_number=1, name='Season 1')
        watched = Episode.objects.create(
            season=season,
            tmdb_id=330110,
            episode_number=1,
            name='Watched Episode',
            air_date=today - timedelta(days=1),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=330113,
            episode_number=4,
            name='Already Aired Today',
            air_date=today,
            broadcast_start=timezone.now() - timedelta(hours=1),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=330112,
            episode_number=2,
            name='Later Broadcast',
            air_date=today + timedelta(days=1),
            broadcast_start=timezone.now() + timedelta(days=1, hours=2),
        )
        Episode.objects.create(
            season=season,
            tmdb_id=330111,
            episode_number=3,
            name='Earlier Broadcast',
            air_date=today + timedelta(days=1),
            broadcast_start=timezone.now() + timedelta(days=1, hours=1),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=show.tmdb_id,
            season_number=season.season_number,
            episode_number=watched.episode_number,
        )

        response = self.client.get('/api/tracking/upcoming/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['name'] for item in response.data],
            ['Earlier Broadcast', 'Later Broadcast'],
        )

    def test_up_next_excludes_season_zero(self):
        from media.models import Episode, Season, TVShow

        show = TVShow.objects.create(tmdb_id=3001, name='Show With Specials')
        season0 = Season.objects.create(show=show, tmdb_id=30010, season_number=0, name='Specials')
        season1 = Season.objects.create(show=show, tmdb_id=30011, season_number=1, name='Season 1')

        Episode.objects.create(season=season0, tmdb_id=300101, episode_number=1, name='Special 1', air_date='2024-01-01')
        Episode.objects.create(season=season0, tmdb_id=300102, episode_number=2, name='Special 2', air_date='2024-01-02')
        Episode.objects.create(season=season1, tmdb_id=300111, episode_number=1, name='Episode 1', air_date='2024-01-03')
        Episode.objects.create(season=season1, tmdb_id=300112, episode_number=2, name='Episode 2', air_date='2024-01-04')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=3001,
            season_number=0,
            episode_number=1,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=3001,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['next_episode']['season_number'], 1)
        self.assertEqual(response.data[0]['next_episode']['episode_number'], 2)

    def test_upcoming_excludes_season_zero(self):
        from media.models import Episode, Season, TVShow

        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=3002, name='Upcoming Specials')
        season0 = Season.objects.create(show=show, tmdb_id=30020, season_number=0, name='Specials')
        season1 = Season.objects.create(show=show, tmdb_id=30021, season_number=1, name='Season 1')

        Episode.objects.create(season=season0, tmdb_id=300201, episode_number=1, name='Upcoming Special', air_date=today + timedelta(days=1))
        Episode.objects.create(
            season=season1,
            tmdb_id=300211,
            episode_number=2,
            name='Upcoming Episode',
            air_date=today + timedelta(days=2),
            episode_type='season premiere',
        )
        Episode.objects.create(
            season=season1,
            tmdb_id=300210,
            episode_number=1,
            name='Watched Episode',
            air_date=today - timedelta(days=1),
        )

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=3002,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/upcoming/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['season_number'], 1)
        self.assertEqual(response.data[0]['episode_type'], 'season premiere')


class SeasonPosterCardsTests(BaseTestCase):
    """Season posters surface in cards, falling back to the show poster."""

    def setUp(self):
        super().setUp()
        self.show = TVShow.objects.create(
            tmdb_id=8001,
            name='Season Poster Show',
            poster_path='/show-poster.jpg',
            first_air_date='2024-01-01',
        )
        self.season1 = Season.objects.create(
            show=self.show,
            tmdb_id=80011,
            season_number=1,
            name='Season 1',
            poster_path='/season1-poster.jpg',
        )
        self.season2 = Season.objects.create(
            show=self.show,
            tmdb_id=80012,
            season_number=2,
            name='Season 2',
            poster_path='',
        )

    def test_history_episode_card_uses_season_poster(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8001,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['poster_path'], '/season1-poster.jpg')
        self.assertEqual(entries[0]['poster_url'], 'https://image.tmdb.org/t/p/w500/season1-poster.jpg')

    def test_history_episode_card_falls_back_to_show_poster_when_season_poster_blank(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8001,
            season_number=2,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(entries[0]['poster_path'], '/show-poster.jpg')
        self.assertEqual(entries[0]['poster_url'], 'https://image.tmdb.org/t/p/w500/show-poster.jpg')

    def test_history_episode_card_falls_back_to_show_poster_when_season_missing(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8001,
            season_number=5,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(entries[0]['poster_path'], '/show-poster.jpg')

    def test_history_movie_card_keeps_movie_poster(self):
        Movie.objects.create(tmdb_id=8002, title='Poster Movie', poster_path='/movie-poster.jpg')
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=8002,
        )

        response = self.client.get('/api/tracking/history/?media_type=movie')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(entries[0]['poster_path'], '/movie-poster.jpg')

    def test_up_next_uses_next_season_poster(self):
        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=8101, name='Up Next Poster Show', poster_path='/un-show.jpg')
        season1 = Season.objects.create(show=show, tmdb_id=81011, season_number=1, name='Season 1', poster_path='/un-s1.jpg')
        season2 = Season.objects.create(show=show, tmdb_id=81012, season_number=2, name='Season 2', poster_path='/un-s2.jpg')
        Episode.objects.create(season=season1, tmdb_id=810111, episode_number=1, name='S1E1', air_date=today - timedelta(days=3))
        Episode.objects.create(season=season2, tmdb_id=810121, episode_number=1, name='S2E1', air_date=today - timedelta(days=1))
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8101,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data if entry['tmdb_id'] == 8101)
        self.assertEqual(item['next_episode']['season_number'], 2)
        self.assertEqual(item['poster_path'], '/un-s2.jpg')
        self.assertEqual(item['poster_url'], 'https://image.tmdb.org/t/p/w500/un-s2.jpg')

    def test_up_next_falls_back_to_show_poster_when_next_season_poster_blank(self):
        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=8201, name='Blank Season Show', poster_path='/blank-un-show.jpg')
        season1 = Season.objects.create(show=show, tmdb_id=82011, season_number=1, name='Season 1', poster_path='')
        Episode.objects.create(season=season1, tmdb_id=820111, episode_number=1, name='E1', air_date=today - timedelta(days=3))
        Episode.objects.create(season=season1, tmdb_id=820112, episode_number=2, name='E2', air_date=today - timedelta(days=1))
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8201,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data if entry['tmdb_id'] == 8201)
        self.assertEqual(item['poster_path'], '/blank-un-show.jpg')
        self.assertEqual(item['poster_url'], 'https://image.tmdb.org/t/p/w500/blank-un-show.jpg')

    def test_upcoming_uses_episode_season_poster(self):
        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=8301, name='Upcoming Poster Show', poster_path='/up-show.jpg')
        season1 = Season.objects.create(show=show, tmdb_id=83011, season_number=1, name='Season 1', poster_path='/up-s1.jpg')
        Episode.objects.create(
            season=season1,
            tmdb_id=830111,
            episode_number=2,
            name='Next Week',
            air_date=today + timedelta(days=6),
        )
        Episode.objects.create(
            season=season1,
            tmdb_id=830110,
            episode_number=1,
            name='Watched Episode',
            air_date=today - timedelta(days=1),
        )
        UserMediaStatus.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=8301,
            status='watching',
            watched_episodes=1,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8301,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/upcoming/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['poster_path'], '/up-s1.jpg')
        self.assertEqual(response.data[0]['poster_url'], 'https://image.tmdb.org/t/p/w500/up-s1.jpg')

    def test_user_stats_recent_activity_uses_season_poster_and_episode_type(self):
        Episode.objects.create(
            season=self.season1,
            tmdb_id=80011,
            episode_number=1,
            name='Poster Episode',
            episode_type='finale',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=8001,
            season_number=1,
            episode_number=1,
        )

        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        recent = response.data['recent_activity']
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]['poster_path'], '/season1-poster.jpg')
        self.assertEqual(recent[0]['poster_url'], 'https://image.tmdb.org/t/p/w500/season1-poster.jpg')
        self.assertEqual(recent[0]['episode_type'], 'finale')


class ProgressListTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        today = timezone.now().date()

        genre_drama = Genre.objects.create(tmdb_id=501, name='Drama')
        genre_scifi = Genre.objects.create(tmdb_id=502, name='Sci-Fi')

        show_a = TVShow.objects.create(
            tmdb_id=4001,
            name='Alpha Show',
            poster_path='/alpha.jpg',
            number_of_seasons=1,
            networks='HBO, Max',
            episode_runtime=42,
            vote_count=150,
            status='Ended',
        )
        show_a.genres.add(genre_drama)
        season_a = Season.objects.create(show=show_a, tmdb_id=4101, season_number=1, name='Season 1')
        Episode.objects.create(season=season_a, tmdb_id=4111, episode_number=1, name='A1', air_date=today - timedelta(days=20), runtime=42)
        Episode.objects.create(
            season=season_a,
            tmdb_id=4112,
            episode_number=2,
            name='A2',
            air_date=today - timedelta(days=2),
            runtime=40,
            episode_type='finale',
            vote_average=8.6,
            vote_count=210,
        )
        Episode.objects.create(season=season_a, tmdb_id=4113, episode_number=3, name='A3', air_date=today + timedelta(days=4), runtime=43)

        show_b = TVShow.objects.create(
            tmdb_id=4002,
            name='Beta Show',
            poster_path='/beta.jpg',
            number_of_seasons=1,
            networks='Netflix',
            vote_count=900,
            status='Ended',
        )
        show_b.genres.add(genre_scifi)
        season_b = Season.objects.create(show=show_b, tmdb_id=4201, season_number=1, name='Season 1')
        Episode.objects.create(season=season_b, tmdb_id=4211, episode_number=1, name='B1', air_date=today - timedelta(days=40), runtime=55)
        Episode.objects.create(season=season_b, tmdb_id=4212, episode_number=2, name='B2', air_date=today - timedelta(days=30), runtime=55)

        show_c = TVShow.objects.create(
            tmdb_id=4003,
            name='Gamma Show',
            poster_path='/gamma.jpg',
            number_of_seasons=1,
            networks='AMC',
            vote_count=80,
            status='Ended',
        )
        show_c.genres.add(genre_drama, genre_scifi)
        season_c = Season.objects.create(show=show_c, tmdb_id=4301, season_number=1, name='Season 1')
        Episode.objects.create(season=season_c, tmdb_id=4311, episode_number=1, name='C1', air_date=today - timedelta(days=14), runtime=30)
        Episode.objects.create(season=season_c, tmdb_id=4312, episode_number=2, name='C2', air_date=today - timedelta(days=10), runtime=30)

        TVShow.objects.create(
            tmdb_id=4004,
            name='Delta Show',
            poster_path='/delta.jpg',
            number_of_seasons=1,
            networks='',
            vote_count=0,
            status='Returning Series',
        )
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=4004, status='plan_to_watch', status_changed_at=timezone.now())

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=4001,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 10, 10, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=4002,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 8, 10, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=4002,
            season_number=1,
            episode_number=2,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 9, 10, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=4003,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 7, 10, 0, 0)),
        )
        UserMediaStatus.objects.update_or_create(
            user=self.user,
            media_type='tv',
            tmdb_id=4003,
            defaults={
                'status': 'dropped',
                'watched_episodes': 1,
                'total_episodes': 2,
                'progress_percent': 50,
                'dropped_at': timezone.make_aware(timezone.datetime(2026, 1, 11, 10, 0, 0)),
                'status_changed_at': timezone.make_aware(timezone.datetime(2026, 1, 11, 10, 0, 0)),
            },
        )

        Rating.objects.create(user=self.user, media_type='tv', tmdb_id=4002, score=8)

    def test_progress_list_includes_started_shows_only(self):
        response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003, 4004})

    def test_progress_list_includes_watchlist_only_shows_as_plan_to_watch(self):
        response = self.client.get('/api/tracking/my-shows/?status=plan_to_watch')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tmdb_id'], 4004)
        self.assertEqual(items[0]['status'], 'plan_to_watch')
        self.assertIsNone(items[0]['next_episode'])
        self.assertIn('upcoming_episode', items[0])
        self.assertIn('last_watched_episode', items[0])
        self.assertIn('episodes_left', items[0])
        self.assertIn('runtime_left_minutes', items[0])
        self.assertIn('progress_percent', items[0])

    def test_plan_to_watch_shows_include_progress_and_next_episode(self):
        show = TVShow.objects.get(tmdb_id=4004)
        season = Season.objects.create(show=show, tmdb_id=4401, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=44011,
            episode_number=1,
            name='Delta Episode',
            air_date=timezone.localdate() - timedelta(days=1),
            runtime=42,
        )
        refresh_show_status(self.user.id, 4004)

        response = self.client.get('/api/tracking/my-shows/?status=plan_to_watch')

        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertEqual(item['status'], 'plan_to_watch')
        self.assertEqual(item['watched_episodes'], 0)
        self.assertEqual(item['total_episodes'], 1)
        self.assertEqual(item['progress_percent'], 0)
        self.assertEqual(item['episodes_left'], 1)
        self.assertEqual(item['runtime_left_minutes'], 42)
        self.assertEqual(item['next_episode']['episode_number'], 1)
        self.assertIsNone(item['started_at'])
        self.assertIsNone(item['last_watched_at'])

    def test_plan_to_watch_row_excluded_from_other_status_filters(self):
        watching = self.client.get('/api/tracking/my-shows/?status=watching')
        self.assertEqual(watching.status_code, 200)
        self.assertNotIn(4004, {item['tmdb_id'] for item in watching.data['results']})

        watched = self.client.get('/api/tracking/my-shows/?status=watched')
        self.assertEqual(watched.status_code, 200)
        self.assertNotIn(4004, {item['tmdb_id'] for item in watched.data['results']})

        planned = self.client.get('/api/tracking/my-shows/?status=plan_to_watch')
        self.assertEqual(planned.status_code, 200)
        self.assertEqual([item['tmdb_id'] for item in planned.data['results']], [4004])

    def test_plan_to_watch_row_sorts_by_progress_fields(self):
        for sort in ('episodes_left', 'last_watched'):
            response = self.client.get(f'/api/tracking/my-shows/?sort={sort}')
            self.assertEqual(response.status_code, 200)
            by_id = {item['tmdb_id']: item for item in response.data['results']}
            self.assertIn(4004, by_id)
            self.assertIn('episodes_left', by_id[4004])
            self.assertIn('runtime_left_minutes', by_id[4004])
            self.assertIn('progress_percent', by_id[4004])

        response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(4004, [item['tmdb_id'] for item in response.data['results']])

    def test_plan_to_watch_row_with_future_only_episodes_has_no_next_episode(self):
        show = TVShow.objects.get(tmdb_id=4004)
        season = Season.objects.create(show=show, tmdb_id=4402, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=44021,
            episode_number=1,
            name='Future Episode',
            air_date=timezone.localdate() + timedelta(days=5),
            runtime=42,
        )
        refresh_show_status(self.user.id, 4004)

        response = self.client.get('/api/tracking/my-shows/?status=plan_to_watch')

        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertEqual(item['status'], 'plan_to_watch')
        self.assertIsNone(item['next_episode'])
        self.assertEqual(item['watched_episodes'], 0)
        self.assertEqual(item['total_episodes'], 0)
        self.assertEqual(item['progress_percent'], 0)
        self.assertEqual(item['episodes_left'], 0)

    def test_plan_to_watch_row_with_unknown_runtimes_sets_flag(self):
        show = TVShow.objects.get(tmdb_id=4004)
        season = Season.objects.create(show=show, tmdb_id=4403, season_number=1, name='Season 1')
        Episode.objects.create(
            season=season,
            tmdb_id=44031,
            episode_number=1,
            name='Mystery Episode',
            air_date=timezone.localdate() - timedelta(days=1),
            runtime=None,
        )
        refresh_show_status(self.user.id, 4004)

        response = self.client.get('/api/tracking/my-shows/?status=plan_to_watch')

        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]
        self.assertEqual(item['status'], 'plan_to_watch')
        self.assertEqual(item['episodes_left'], 1)
        self.assertEqual(item['runtime_left_minutes'], 0)
        self.assertTrue(item['runtime_left_has_unknown'])

    def test_progress_list_filters_missing_rating(self):
        response = self.client.get('/api/tracking/my-shows/?missing_rating=true')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertTrue(all(item['user_rating'] is None for item in items))
        self.assertEqual({item['tmdb_id'] for item in items}, {4001, 4003})

    def test_progress_list_filters_has_next_episode(self):
        response = self.client.get('/api/tracking/my-shows/?has_next_episode=true')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual({item['tmdb_id'] for item in items}, {4001, 4003})
        self.assertTrue(all(item['next_episode'] is not None for item in items))

        unfiltered = self.client.get('/api/tracking/my-shows/')
        by_id = {item['tmdb_id']: item for item in unfiltered.data['results']}
        self.assertIsNone(by_id[4002]['next_episode'])
        self.assertIsNotNone(by_id[4003]['next_episode'])

    def test_progress_list_filters_without_next_episode(self):
        response = self.client.get('/api/tracking/my-shows/?has_next_episode=false')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['tmdb_id'] for item in response.data['results']}, {4002, 4004})

    def test_progress_list_query_count_stays_bounded(self):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(context), 60)

    def test_progress_list_progress_and_next_episode_agree(self):
        response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        for item in response.data['results']:
            if item['status'] == 'plan_to_watch':
                continue
            self.assertEqual((item['episodes_left'] or 0) > 0, item['next_episode'] is not None)
            self.assertEqual((item['progress_percent'] or 0) == 100, (item['episodes_left'] or 0) == 0)

    def test_progress_list_filters_genres_multi(self):
        response = self.client.get('/api/tracking/my-shows/?genres=Drama&genres=Sci-Fi')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003})

    def test_progress_list_filters_status_and_search(self):
        response = self.client.get('/api/tracking/my-shows/?status=dropped&search=gamma')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['status'], 'dropped')
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_filters_user_status_multi_select(self):
        response = self.client.get('/api/tracking/my-shows/?status=watching&status=watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002})

    def test_progress_list_filters_provider_status_multi_select(self):
        response = self.client.get('/api/tracking/my-shows/?provider_status=Ended&provider_status=Returning%20Series')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003, 4004})

    def test_progress_list_includes_available_provider_statuses(self):
        response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        statuses = response.data.get('available_provider_statuses', [])
        self.assertEqual(statuses, ['Ended', 'Returning Series'])

    def test_progress_list_filters_watching_by_status(self):
        response = self.client.get('/api/tracking/my-shows/?status=watching')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual([item['tmdb_id'] for item in items], [4001])

    def test_progress_list_filters_watched_by_status(self):
        response = self.client.get('/api/tracking/my-shows/?status=watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual([item['tmdb_id'] for item in items], [4002])

    def test_progress_list_sorts_time_left(self):
        response = self.client.get('/api/tracking/my-shows/?sort=time_left')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_sorts_last_watched(self):
        response = self.client.get('/api/tracking/my-shows/?sort=last_watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4001)

    def test_progress_list_sorts_episodes_left(self):
        response = self.client.get('/api/tracking/my-shows/?sort=episodes_left')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_aggregates_all_remaining_episodes_and_runtime(self):
        Episode.objects.filter(tmdb_id=4113).update(air_date=timezone.now().date() - timedelta(days=1))
        refresh_show_status(self.user.id, 4001)

        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        item = response.data['results'][0]

        self.assertEqual(item['episodes_left'], 2)
        self.assertEqual(item['runtime_left_minutes'], 83)
        self.assertFalse(item['runtime_left_has_unknown'])

    def test_progress_list_filters_upcoming_and_new(self):
        response = self.client.get('/api/tracking/my-shows/?has_upcoming=true&is_new=true')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tmdb_id'], 4001)
        self.assertTrue(items[0]['has_upcoming_episode'])
        self.assertTrue(items[0]['is_new'])

    def test_progress_list_includes_total_runtime_minutes(self):
        response = self.client.get('/api/tracking/my-shows/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_runtime_minutes', response.data)
        # Alpha 42+40+43, Beta 55+55, Gamma 30+30; Delta has no episodes.
        self.assertEqual(response.data['total_runtime_minutes'], 295)

    def test_progress_list_total_runtime_minutes_respects_filters(self):
        response = self.client.get('/api/tracking/my-shows/?status=watched')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_runtime_minutes', response.data)
        self.assertEqual(response.data['total_runtime_minutes'], 110)

    def test_progress_list_includes_last_watched_episode_code_parts(self):
        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4001)
        self.assertEqual(item['last_watched_episode']['season_number'], 1)
        self.assertEqual(item['last_watched_episode']['episode_number'], 1)

    def test_progress_list_includes_started_at_from_oldest_watch_entry(self):
        response = self.client.get('/api/tracking/my-shows/?search=beta')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4002)
        self.assertTrue(str(item['started_at']).startswith('2026-01-08'))

    def test_progress_list_includes_next_episode_provider_rating_fields(self):
        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4001)
        self.assertEqual(item['next_episode']['vote_average'], 8.6)
        self.assertEqual(item['next_episode']['vote_count'], 210)

    def test_progress_list_includes_next_episode_type(self):
        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['next_episode']['episode_type'], 'finale')

    def test_progress_list_includes_provider_show_status(self):
        response = self.client.get('/api/tracking/my-shows/?search=beta')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4002)
        self.assertEqual(item['provider_status'], 'Ended')

    def test_progress_list_includes_episode_runtime(self):
        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['episode_runtime'], 42)

    def test_progress_list_includes_number_of_seasons(self):
        response = self.client.get('/api/tracking/my-shows/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['number_of_seasons'], 1)


class MyMoviesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.authenticate()

        genre_action = Genre.objects.create(tmdb_id=28, name='Action')
        genre_drama = Genre.objects.create(tmdb_id=18, name='Drama')

        Movie.objects.create(
            tmdb_id=5001,
            title='Alpha Movie',
            poster_path='/alpha.jpg',
            release_date=date(2020, 1, 1),
            runtime=120,
            vote_average=7.5,
            vote_count=100,
        ).genres.add(genre_action)

        Movie.objects.create(
            tmdb_id=5002,
            title='Beta Movie',
            poster_path='/beta.jpg',
            release_date=date(2021, 6, 15),
            runtime=90,
            vote_average=8.0,
            vote_count=200,
        ).genres.add(genre_drama)

        Movie.objects.create(
            tmdb_id=5003,
            title='Gamma Movie',
            poster_path='/gamma.jpg',
            release_date=None,
            runtime=None,
            vote_average=6.0,
            vote_count=50,
        )

        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=5001, status='watched')
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=5002, status='plan_to_watch')
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=5003, status='dropped')

        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=5001,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 5, 10, 0, 0)),
        )
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=5002, score=9)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/tracking/my-movies/')
        self.assertEqual(response.status_code, 401)

    def test_includes_all_tracked_statuses(self):
        response = self.client.get('/api/tracking/my-movies/')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual({item['tmdb_id'] for item in items}, {5001, 5002, 5003})
        status_by_id = {item['tmdb_id']: item['status'] for item in items}
        self.assertEqual(status_by_id[5001], 'watched')
        self.assertEqual(status_by_id[5002], 'plan_to_watch')
        self.assertEqual(status_by_id[5003], 'dropped')

    def test_empty_library_shape(self):
        UserMediaStatus.objects.all().delete()
        response = self.client.get('/api/tracking/my-movies/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['available_genres'], [])
        self.assertEqual(response.data['total_runtime_minutes'], 0)

    def test_item_payload_fields(self):
        response = self.client.get('/api/tracking/my-movies/?search=alpha')
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['title'], 'Alpha Movie')
        self.assertEqual(item['poster_url'], 'https://image.tmdb.org/t/p/w500/alpha.jpg')
        self.assertEqual(item['release_date'], date(2020, 1, 1))
        self.assertEqual(item['runtime'], 120)
        self.assertEqual(item['genres'], ['Action'])
        self.assertEqual(item['vote_average'], 7.5)
        self.assertEqual(item['user_rating'], None)

    def test_filters_status_multi_select(self):
        response = self.client.get('/api/tracking/my-movies/?status=watched&status=plan_to_watch')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual({item['tmdb_id'] for item in items}, {5001, 5002})

    def test_filters_genres_multi_select(self):
        response = self.client.get('/api/tracking/my-movies/?genres=Drama&genres=Action')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual({item['tmdb_id'] for item in items}, {5001, 5002})

    def test_filters_search_by_title(self):
        response = self.client.get('/api/tracking/my-movies/?search=beta')
        items = response.data['results']
        self.assertEqual([item['tmdb_id'] for item in items], [5002])

    def test_filters_missing_rating(self):
        response = self.client.get('/api/tracking/my-movies/?missing_rating=true')
        items = response.data['results']
        self.assertEqual({item['tmdb_id'] for item in items}, {5001, 5003})

    def test_default_sort_is_watched_date_desc(self):
        response = self.client.get('/api/tracking/my-movies/')
        # Watched movie first, unrated/unwatched ties broken by title.
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5001, 5002, 5003])

    def test_sorts_title_desc(self):
        response = self.client.get('/api/tracking/my-movies/?sort=title&direction=desc')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5003, 5002, 5001])

    def test_sorts_release_date_asc_nulls_last(self):
        response = self.client.get('/api/tracking/my-movies/?sort=release_date&direction=asc')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5001, 5002, 5003])

    def test_sorts_release_date_defaults_to_desc(self):
        response = self.client.get('/api/tracking/my-movies/?sort=release_date')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5003, 5002, 5001])

    def test_sorts_user_rating_rated_first_on_desc(self):
        response = self.client.get('/api/tracking/my-movies/?sort=user_rating&direction=desc')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5002, 5001, 5003])

    def test_sorts_provider_rating_desc_by_default(self):
        response = self.client.get('/api/tracking/my-movies/?sort=provider_rating')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5002, 5001, 5003])

    def test_sorts_user_rating_desc_by_default(self):
        response = self.client.get('/api/tracking/my-movies/?sort=user_rating')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5002, 5001, 5003])

    def test_sorts_missing_user_rating_as_zero(self):
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=5001, score=1)
        response = self.client.get('/api/tracking/my-movies/?sort=user_rating&direction=asc')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5003, 5001, 5002])

    def test_sorts_runtime_asc(self):
        response = self.client.get('/api/tracking/my-movies/?sort=runtime')
        self.assertEqual([item['tmdb_id'] for item in response.data['results']], [5002, 5001, 5003])

    def test_sorts_watched_date_watched_first_on_desc(self):
        response = self.client.get('/api/tracking/my-movies/?sort=watched_date&direction=desc')
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 5001)
        self.assertIsNotNone(items[0]['last_watched_at'])

    def test_total_runtime_minutes_sums_all_items(self):
        response = self.client.get('/api/tracking/my-movies/')
        # Alpha 120 (watched) + Beta 90 (planned) + Gamma null (dropped, counts as 0).
        self.assertEqual(response.data['total_runtime_minutes'], 210)

    def test_watched_movie_reports_last_watched_at(self):
        response = self.client.get('/api/tracking/my-movies/?search=alpha')
        item = response.data['results'][0]
        self.assertEqual(
            item['last_watched_at'],
            timezone.make_aware(timezone.datetime(2026, 1, 5, 10, 0, 0)),
        )

    def test_available_genres(self):
        response = self.client.get('/api/tracking/my-movies/')
        self.assertEqual(response.data['available_genres'], ['Action', 'Drama'])

    def test_pagination_envelope(self):
        response = self.client.get('/api/tracking/my-movies/?page=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(len(response.data['results']), 3)
