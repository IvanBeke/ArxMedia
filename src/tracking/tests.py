import io
import json
import zipfile
from datetime import timedelta
from unittest.mock import patch

from celery.schedules import crontab
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from media.models import Episode, Movie, Season, TVShow
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    UserSeasonStatus,
    UserTvShowStatus,
    WatchEntry,
    Watchlist,
)

User = get_user_model()


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='user2@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self._tmdb_patchers = [
            patch('tracking.views.tmdb.sync_movie', return_value=None),
            patch('tracking.views.tmdb.sync_tv_show', return_value=None),
            patch('tracking.tasks.tmdb.sync_movie', return_value=None),
            patch('tracking.tasks.tmdb.sync_tv_show', return_value=None),
            patch('tracking.tasks.tmdb.sync_season', return_value=None),
        ]
        for patcher in self._tmdb_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.authenticate()

    def authenticate(self, user=None):
        if user is None:
            user = self.user
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')


class WatchEntryTests(BaseTestCase):
    def test_create_movie_watched(self):
        data = {'media_type': 'movie', 'tmdb_id': 123, 'status': 'watched'}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WatchEntry.objects.count(), 1)

    def test_create_episode_watched(self):
        data = {'media_type': 'episode', 'tmdb_id': 456, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)

    def test_create_show_watching_rejected(self):
        data = {'media_type': 'show', 'tmdb_id': 789, 'status': 'watching'}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 400)

    def test_remove_from_watchlist_on_watch(self):
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=999)
        self.assertEqual(Watchlist.objects.count(), 1)
        data = {'media_type': 'movie', 'tmdb_id': 999, 'status': 'watched'}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Watchlist.objects.count(), 0)

    def test_drop_show(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=789,
            status='watched', season_number=1, episode_number=1
        )
        response = self.client.post('/api/tracking/shows/drop/', {'tmdb_id': 789})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['dropped'])
        self.assertEqual(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=789,
                season_number=1,
                episode_number=1,
                status='watched',
            ).count(),
            1,
        )
        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=789,
                status='dropped',
                season_number__isnull=True,
                episode_number__isnull=True,
            ).exists()
        )

    def test_drop_show_not_found(self):
        response = self.client.post('/api/tracking/shows/drop/', {'tmdb_id': 999})
        self.assertEqual(response.status_code, 200)

    def test_history_list_orders_by_watched_at_newest_first(self):
        older = timezone.make_aware(timezone.datetime(2026, 1, 1, 10, 0, 0))
        newer = timezone.make_aware(timezone.datetime(2026, 1, 2, 10, 0, 0))

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=500,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at=older,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=600,
            status='watched',
            watched_at=newer,
        )

        response = self.client.get('/api/tracking/history/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 600)
        self.assertEqual(data[1]['tmdb_id'], 500)

    def test_history_list_filters_media_type(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=700,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=701,
            status='watched',
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/?media_type=movie')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['media_type'], 'movie')
        self.assertEqual(data[0]['tmdb_id'], 701)

    def test_history_list_oldest_order(self):
        older = timezone.make_aware(timezone.datetime(2026, 2, 1, 10, 0, 0))
        newer = timezone.make_aware(timezone.datetime(2026, 2, 3, 10, 0, 0))

        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=800,
            status='watched',
            watched_at=newer,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=801,
            status='watched',
            watched_at=older,
        )

        response = self.client.get('/api/tracking/history/?order=oldest')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 801)
        self.assertEqual(data[1]['tmdb_id'], 800)


class RatingTests(BaseTestCase):
    def test_create_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=123,
            status='watched',
            watched_at=timezone.now(),
        )
        data = {'media_type': 'movie', 'tmdb_id': 123, 'score': 8}
        response = self.client.post('/api/tracking/ratings/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Rating.objects.count(), 1)

    def test_upsert_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=123,
            status='watched',
            watched_at=timezone.now(),
        )
        Rating.objects.create(user=self.user, media_type='movie', tmdb_id=123, score=5)
        data = {'media_type': 'movie', 'tmdb_id': 123, 'score': 9}
        response = self.client.post('/api/tracking/ratings/', data)
        self.assertEqual(response.status_code, 201)
        rating = Rating.objects.first()
        self.assertEqual(rating.score, 9)

    def test_reject_movie_rating_when_not_watched(self):
        response = self.client.post('/api/tracking/ratings/', {'media_type': 'movie', 'tmdb_id': 321, 'score': 7})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Rating.objects.count(), 0)

    def test_reject_movie_rating_when_only_in_watchlist(self):
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=456)
        response = self.client.post('/api/tracking/ratings/', {'media_type': 'movie', 'tmdb_id': 456, 'score': 7})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Rating.objects.count(), 0)

    def test_reject_tv_rating_when_none_or_watchlist(self):
        response_none = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 901, 'score': 7})
        self.assertEqual(response_none.status_code, 400)

        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=902)
        response_watchlist = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 902, 'score': 8})
        self.assertEqual(response_watchlist.status_code, 400)

    def test_allow_tv_rating_for_watching_watched_and_dropped(self):
        UserTvShowStatus.objects.create(user=self.user, tmdb_id=910, status='watching')
        UserTvShowStatus.objects.create(user=self.user, tmdb_id=911, status='watched')
        UserTvShowStatus.objects.create(user=self.user, tmdb_id=912, status='dropped')

        response_watching = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 910, 'score': 8})
        response_watched = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 911, 'score': 9})
        response_dropped = self.client.post('/api/tracking/ratings/', {'media_type': 'tv', 'tmdb_id': 912, 'score': 6})

        self.assertEqual(response_watching.status_code, 201)
        self.assertEqual(response_watched.status_code, 201)
        self.assertEqual(response_dropped.status_code, 201)


class WatchlistTests(BaseTestCase):
    def test_add_to_watchlist(self):
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 201)

    @patch('tracking.views.tmdb.sync_movie')
    def test_add_to_watchlist_syncs_movie_metadata(self, mock_sync_movie):
        mock_sync_movie.return_value = None
        data = {'media_type': 'movie', 'tmdb_id': 124}

        response = self.client.post('/api/tracking/watchlist/', data)

        self.assertEqual(response.status_code, 201)
        mock_sync_movie.assert_called_once_with(124)

    @patch('tracking.views.tmdb.sync_tv_show')
    def test_add_to_watchlist_syncs_tv_metadata(self, mock_sync_tv_show):
        mock_sync_tv_show.return_value = None
        data = {'media_type': 'tv', 'tmdb_id': 457}

        response = self.client.post('/api/tracking/watchlist/', data)

        self.assertEqual(response.status_code, 201)
        mock_sync_tv_show.assert_called_once_with(457)

    def test_block_watched_content_to_watchlist(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123,
            status='watched', watched_at=timezone.now()
        )
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_block_show_with_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=456,
            season_number=1, episode_number=1, status='watched'
        )
        data = {'media_type': 'tv', 'tmdb_id': 456}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_allow_show_without_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=789,
            season_number=1, episode_number=1, status='watching'
        )
        data = {'media_type': 'tv', 'tmdb_id': 789}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 201)

    def test_watchlist_list_includes_movie_user_status_and_dates(self):
        Movie.objects.create(
            tmdb_id=1101,
            title='Movie For Watchlist',
            release_date=timezone.datetime(2024, 5, 1).date(),
        )
        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=1101)

        response = self.client.get('/api/tracking/watchlist/?media_type=movie')
        self.assertEqual(response.status_code, 200)

        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['tmdb_id'], 1101)
        self.assertEqual(entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(str(entry['release_date']), '2024-05-01')
        self.assertIsNone(entry['first_air_date'])

    def test_watchlist_list_includes_tv_plan_to_watch_status(self):
        TVShow.objects.create(
            tmdb_id=2202,
            name='Show For Watchlist',
            first_air_date=timezone.datetime(2023, 8, 10).date(),
        )
        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=2202)

        response = self.client.get('/api/tracking/watchlist/?media_type=tv')
        self.assertEqual(response.status_code, 200)

        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['tmdb_id'], 2202)
        self.assertEqual(entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(str(entry['first_air_date']), '2023-08-10')
        self.assertIsNone(entry['release_date'])


class EpisodeTests(BaseTestCase):
    def test_mark_episode_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/mark/', data)
        self.assertEqual(response.status_code, 201)

    def test_unmark_episode_watched(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1, status='watched'
        )
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/unmark/', data)
        self.assertEqual(response.status_code, 200)

    def test_get_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1, status='watched'
        )
        response = self.client.get('/api/tracking/episodes/watched/?tmdb_id=123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['episodes']), 1)


class SeasonTests(BaseTestCase):
    def test_mark_season_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1}
        response = self.client.post('/api/tracking/seasons/mark/', data)
        self.assertEqual(response.status_code, 404)

    def test_unmark_season_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1}
        response = self.client.post('/api/tracking/seasons/unmark/', data)
        self.assertEqual(response.status_code, 200)


class MaterializedStatusTests(BaseTestCase):
    def test_dropped_show_moves_to_watching_when_new_episode_is_watched(self):
        show = TVShow.objects.create(tmdb_id=9100, name='Resume Show', status='Ended')
        season = Season.objects.create(show=show, tmdb_id=91001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=910011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=910012, episode_number=2, name='Ep 2', air_date='2024-01-02')
        Episode.objects.create(season=season, tmdb_id=910013, episode_number=3, name='Ep 3', air_date='2024-01-03')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9100,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 1, 10, 0, 0)),
        )
        self.client.post('/api/tracking/shows/drop/', {'tmdb_id': 9100})
        self.client.post('/api/tracking/episodes/mark/', {'tmdb_id': 9100, 'season_number': 1, 'episode_number': 2})

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=9100)
        self.assertEqual(show_status.status, 'watching')

    def test_non_final_tmdb_show_never_becomes_watched(self):
        show = TVShow.objects.create(tmdb_id=9200, name='Ongoing Show', status='Returning Series')
        season = Season.objects.create(show=show, tmdb_id=92001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=920011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=920012, episode_number=2, name='Ep 2', air_date='2024-01-02')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9200,
            season_number=1,
            episode_number=1,
            status='watched',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9200,
            season_number=1,
            episode_number=2,
            status='watched',
        )

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=9200)
        season_status = UserSeasonStatus.objects.get(user=self.user, tmdb_id=9200, season_number=1)
        self.assertEqual(show_status.status, 'watching')
        self.assertEqual(season_status.status, 'watching')

    def test_final_tmdb_show_becomes_watched_when_complete(self):
        show = TVShow.objects.create(tmdb_id=9300, name='Finished Show', status='Canceled')
        season = Season.objects.create(show=show, tmdb_id=93001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=930011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=930012, episode_number=2, name='Ep 2', air_date='2024-01-02')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9300,
            season_number=1,
            episode_number=1,
            status='watched',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9300,
            season_number=1,
            episode_number=2,
            status='watched',
        )

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=9300)
        season_status = UserSeasonStatus.objects.get(user=self.user, tmdb_id=9300, season_number=1)
        self.assertEqual(show_status.status, 'watched')
        self.assertEqual(season_status.status, 'watched')


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
                air_date='2024-01-01'
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
            air_date='2024-02-01'
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
                season_number=1, episode_number=i, status='watched'
            )
        
        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Should return S1E4 as next episode
        self.assertEqual(response.data[0]['next_episode']['season_number'], 1)
        self.assertEqual(response.data[0]['next_episode']['episode_number'], 4)

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
                season_number=1, episode_number=i, status='watched'
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
            status='watched',
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 1, 0, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=999,
            season_number=1,
            episode_number=1,
            status='watched',
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
                status='watched',
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
            status='watched',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2002,
            season_number=1,
            episode_number=1,
            status='watched',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2001,
            season_number=None,
            episode_number=None,
            status='dropped',
        )

        response = self.client.get('/api/tracking/up-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['tmdb_id'], 2002)

    def test_upcoming_empty(self):
        response = self.client.get('/api/tracking/upcoming/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

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
            status='watched',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=3001,
            season_number=1,
            episode_number=1,
            status='watched',
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
        Episode.objects.create(season=season1, tmdb_id=300211, episode_number=1, name='Upcoming Episode', air_date=today + timedelta(days=2))

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=3002,
            season_number=1,
            episode_number=1,
            status='watched',
        )

        response = self.client.get('/api/tracking/upcoming/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['season_number'], 1)


class CustomListTests(BaseTestCase):
    def test_create_list(self):
        data = {'name': 'My Favorite Movies', 'description': 'Best movies ever', 'privacy': 'public'}
        response = self.client.post('/api/tracking/lists/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomList.objects.count(), 1)

    def test_list_privacy_public(self):
        CustomList.objects.create(user=self.user2, name='Public List', privacy='public')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_privacy_private(self):
        CustomList.objects.create(user=self.user2, name='Private List', privacy='private')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

    def test_owner_sees_own_private_list(self):
        CustomList.objects.create(user=self.user, name='My Private List', privacy='private')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_update_list_as_owner(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        data = {'name': 'Updated List', 'privacy': 'followers'}
        response = self.client.patch(f'/api/tracking/lists/{lst.id}/', data)
        self.assertEqual(response.status_code, 200)
        lst.refresh_from_db()
        self.assertEqual(lst.name, 'Updated List')

    def test_cannot_update_others_list(self):
        lst = CustomList.objects.create(user=self.user2, name='Other List')
        data = {'name': 'Hacked'}
        response = self.client.patch(f'/api/tracking/lists/{lst.id}/', data)
        self.assertEqual(response.status_code, 403)

    def test_delete_list_as_owner(self):
        lst = CustomList.objects.create(user=self.user, name='To Delete')
        response = self.client.delete(f'/api/tracking/lists/{lst.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CustomList.objects.count(), 0)


class ListItemTests(BaseTestCase):
    def test_add_item_to_list(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ListItem.objects.count(), 1)

    def test_bulk_add_to_list(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        items = [
            {'media_type': 'movie', 'tmdb_id': 123},
            {'media_type': 'tv', 'tmdb_id': 456}
        ]
        response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', items, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ListItem.objects.count(), 2)

    def test_remove_item_from_list(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        item = ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        response = self.client.delete(f'/api/tracking/lists/{lst.id}/items/{item.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(ListItem.objects.count(), 0)

    def test_sort_list_items_by_date(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=456)
        
        # Default sort should be -added_at (newest first)
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(response.status_code, 200)
        # Should have at least our 2 items
        self.assertGreaterEqual(len(response.data), 2)
        
        # Sort by added_at ascending
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=added_at')
        self.assertEqual(response.status_code, 200)
        
        # Sort by media_type
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=media_type')
        self.assertEqual(response.status_code, 200)

    def test_cannot_access_others_list_items(self):
        lst = CustomList.objects.create(user=self.user2, name='Other List', privacy='private')
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(response.status_code, 403)


class UserStatsTests(BaseTestCase):
    def test_stats_endpoint(self):
        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('movies_watched', response.data)
        self.assertIn('episodes_watched', response.data)

    def test_stats_with_watched_movie(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123,
            status='watched', watched_at=timezone.now()
        )
        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['movies_watched'], 1)

    def test_recent_activity_includes_rating_when_available(self):
        watched_at = timezone.now()
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=999,
            status='watched',
            watched_at=watched_at,
        )
        Rating.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=999,
            score=8,
        )

        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['recent_activity'])
        first = response.data['recent_activity'][0]
        self.assertEqual(first['tmdb_id'], 999)
        self.assertEqual(first['rating'], 8)

    def test_stats_cache_invalidated_on_history_delete(self):
        entry = WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=321,
            status='watched',
            watched_at=timezone.now(),
        )

        warm = self.client.get('/api/tracking/stats/')
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(warm.data['movies_watched'], 1)

        delete_resp = self.client.delete(f'/api/tracking/history/{entry.id}/')
        self.assertEqual(delete_resp.status_code, 204)

        after = self.client.get('/api/tracking/stats/')
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data['movies_watched'], 0)

    def test_stats_cache_invalidated_on_episode_history_delete(self):
        entry = WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=654,
            season_number=1,
            episode_number=1,
            status='watched',
            watched_at=timezone.now(),
        )

        warm = self.client.get('/api/tracking/stats/')
        self.assertEqual(warm.status_code, 200)
        self.assertEqual(warm.data['shows_watching'], 1)

        delete_resp = self.client.delete(f'/api/tracking/history/{entry.id}/')
        self.assertEqual(delete_resp.status_code, 204)

        after = self.client.get('/api/tracking/stats/')
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data['shows_watching'], 0)


class RecommendationsTests(BaseTestCase):
    @patch('tracking.views.tmdb.get_popular_movies')
    @patch('tracking.views.tmdb.get_popular_tv')
    def test_recommendations_exclude_watched_and_watchlist(self, mock_tv, mock_movies):
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=10, status='watched')
        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=20)

        mock_movies.return_value = {'results': [{'id': 10}, {'id': 11}]}
        mock_tv.return_value = {'results': [{'id': 20}, {'id': 21}]}

        response = self.client.get('/api/tracking/recommendations/')
        self.assertEqual(response.status_code, 200)
        movie_ids = [m['id'] for m in response.data['movies']]
        tv_ids = [t['id'] for t in response.data['tv']]
        self.assertNotIn(10, movie_ids)
        self.assertNotIn(20, tv_ids)


class ListCollaborationTest(BaseTestCase):
    def test_add_and_remove_collaborator_and_item_permissions(self):
        lst = CustomList.objects.create(user=self.user, name='Shared List')

        response = self.client.post(f'/api/tracking/lists/{lst.id}/collaborators/', {'user_id': self.user2.id})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ListCollaborator.objects.filter(custom_list=lst, user=self.user2).exists())

        self.authenticate(self.user2)
        add_item = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 987})
        self.assertEqual(add_item.status_code, 201)

        self.authenticate(self.user)
        remove_collab = self.client.delete(f'/api/tracking/lists/{lst.id}/collaborators/{self.user2.id}/')
        self.assertEqual(remove_collab.status_code, 204)


class DataImportExportTests(BaseTestCase):
    def _build_yamtrack_csv(self, rows):
        header = [
            'source',
            'media_type',
            'media_id',
            'season_number',
            'episode_number',
            'status',
            'score',
            'progress',
            'start_date',
            'end_date',
            'progressed_at',
            'created_at',
            'notes',
        ]
        lines = [','.join(header)]
        for row in rows:
            values = [str(row.get(key, '')) for key in header]
            lines.append(','.join(values))
        return ('\n'.join(lines) + '\n').encode('utf-8')

    def test_export_job_creation(self):
        response = self.client.post('/api/tracking/data/export/?format=json', {})
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)

    def test_export_rejects_non_json_format(self):
        response = self.client.post('/api/tracking/data/export/?data_format=csv', {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['format'], 'format must be json')

    def test_import_job_creation(self):
        file_obj = SimpleUploadedFile('import.json', b'{"watch_history": []}', content_type='application/json')
        response = self.client.post('/api/tracking/data/import/?format=json&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)

    def test_zip_import_job_creation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('lists-watchlist.json', '[]')
        file_obj = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')

        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'zip')

    def test_import_requires_source(self):
        file_obj = SimpleUploadedFile('import.csv', b'collection,media_type,tmdb_id\n', content_type='text/csv')
        response = self.client.post('/api/tracking/data/import/?data_format=csv', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_yamtrack_csv_import_job_creation(self):
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 101, 'status': 'Completed'},
        ])
        file_obj = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')

        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'csv')
        self.assertEqual(response.data.get('metadata', {}).get('import_source'), 'yamtrack')

    def test_import_rejects_source_format_mismatch(self):
        file_obj = SimpleUploadedFile('import.json', b'{"watch_history": []}', content_type='application/json')
        response = self.client.post('/api/tracking/data/import/?data_format=json&source=trakt', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_data_jobs_list_scoped_and_ordered(self):
        now = timezone.now()
        old_job = DataTransferJob.objects.create(user=self.user, job_type='import', data_format='json', status='pending')
        new_job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='json', status='done')
        DataTransferJob.objects.create(user=self.user2, job_type='import', data_format='json', status='pending')

        DataTransferJob.objects.filter(id=old_job.id).update(created_at=now - timedelta(days=2))
        DataTransferJob.objects.filter(id=new_job.id).update(created_at=now)

        response = self.client.get('/api/tracking/data/jobs/')
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], new_job.id)
        self.assertEqual(results[1]['id'], old_job.id)

    def test_prepare_zip_import_sets_awaiting_confirmation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps([
                {'type': 'movie', 'movie': {'ids': {'tmdb': 100}}, 'watched_at': '2026-07-01T10:00:00.000Z'}
            ]))
            archive.writestr('lists-watchlist.json', json.dumps([
                {'type': 'movie', 'movie': {'ids': {'tmdb': 200}}}
            ]))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_trakt_zip_import
        prepare_trakt_zip_import(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'awaiting_confirmation')
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.metadata.get('summary', {}).get('watch_history'), 1)
        self.assertEqual(job.metadata.get('summary', {}).get('watchlist'), 1)

    def test_prepare_yamtrack_csv_sets_awaiting_confirmation(self):
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 100, 'status': 'Completed', 'score': '8.4'},
            {'source': 'mal', 'media_type': 'anime', 'media_id': 999, 'status': 'Completed'},
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_yamtrack_csv_import
        prepare_yamtrack_csv_import(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'awaiting_confirmation')
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.metadata.get('import_source'), 'yamtrack')
        self.assertEqual(job.metadata.get('summary', {}).get('watch_history'), 1)
        self.assertEqual(job.metadata.get('summary', {}).get('ratings'), 1)
        self.assertEqual(job.metadata.get('skipped_non_tmdb'), 1)

    def test_confirm_zip_import_requires_awaiting_confirmation(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='pending',
        )
        response = self.client.post(f'/api/tracking/data/jobs/{job.id}/confirm/', {'import_mode': 'new_items'}, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('tracking.tasks.apply_trakt_zip_import.delay')
    def test_confirm_zip_import_starts_apply_task(self, mock_delay):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='awaiting_confirmation',
            metadata={'import_source': 'trakt', 'total_items': 3, 'summary': {'watch_history': 1, 'watchlist': 1, 'ratings': 1}},
        )
        response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'mirror_imported_set'},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertTrue(job.overwrite_existing)
        self.assertEqual(job.metadata.get('import_mode'), 'mirror_imported_set')
        mock_delay.assert_called_once_with(job.id)

    @patch('tracking.tasks.apply_yamtrack_csv_import.delay')
    def test_confirm_yamtrack_csv_starts_apply_task(self, mock_delay):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            metadata={
                'import_source': 'yamtrack',
                'total_items': 2,
                'summary': {'watch_history': 1, 'watchlist': 0, 'ratings': 1},
            },
        )
        response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'update_existing'},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertTrue(job.overwrite_existing)
        self.assertEqual(job.metadata.get('import_mode'), 'update_existing')
        mock_delay.assert_called_once_with(job.id)

    def test_confirm_non_yamtrack_csv_is_rejected(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            metadata={'total_items': 1},
        )
        response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'new_items'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_apply_yamtrack_csv_import_maps_statuses_and_filters_rows(self):
        TVShow.objects.create(tmdb_id=500, name='Mapped Show')
        csv_content = self._build_yamtrack_csv([
            {
                'source': 'tmdb',
                'media_type': 'tv',
                'media_id': 500,
                'status': 'Paused',
                'score': '7.6',
                'progress': '12',
                'progressed_at': '2026-01-05T10:00:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'episode',
                'media_id': 500,
                'season_number': 1,
                'episode_number': 2,
                'status': '',
                'end_date': '2026-02-01T12:30:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'movie',
                'media_id': 601,
                'status': 'Completed',
                'score': '8.5',
                'end_date': '2026-02-03T08:00:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'movie',
                'media_id': 602,
                'status': 'Planning',
                'score': '0',
            },
            {
                'source': 'mal',
                'media_type': 'movie',
                'media_id': 700,
                'status': 'Completed',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='processing',
            input_file=upload,
            metadata={'import_source': 'yamtrack', 'import_mode': 'new_items', 'total_items': 5},
            total_items=5,
        )

        from tracking.tasks import apply_yamtrack_csv_import
        apply_yamtrack_csv_import(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.processed_items, 5)
        self.assertEqual(job.metadata.get('skipped_non_tmdb'), 1)

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=500)
        self.assertEqual(show_status.status, 'watching')

        episode_entry = WatchEntry.objects.get(
            user=self.user,
            media_type='episode',
            tmdb_id=500,
            season_number=1,
            episode_number=2,
        )
        self.assertEqual(episode_entry.status, 'watched')
        self.assertEqual(episode_entry.watched_at.isoformat(), '2026-02-01T12:30:00+00:00')

        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=601, status='watched').exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=601, score=9).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='tv', tmdb_id=500, score=8).exists())
        self.assertFalse(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=602).exists())
        self.assertTrue(Watchlist.objects.filter(user=self.user, media_type='movie', tmdb_id=602).exists())
        self.assertFalse(WatchEntry.objects.filter(user=self.user, tmdb_id=700).exists())

    def test_zip_import_loads_history_watchlist_and_ratings(self):
        watched_history = [
            {
                'type': 'movie',
                'watched_at': '2026-07-01T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 101}},
            },
            {
                'type': 'episode',
                'watched_at': '2026-07-02T10:00:00.000Z',
                'episode': {'season': 2, 'number': 3},
                'show': {'ids': {'tmdb': 202}},
            },
        ]
        watched_movies = [
            {
                'last_watched_at': '2026-07-03T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 303}},
            }
        ]
        watchlist = [
            {'type': 'movie', 'movie': {'ids': {'tmdb': 404}}},
            {'type': 'show', 'show': {'ids': {'tmdb': 505}}},
        ]
        ratings_movies = [
            {'type': 'movie', 'rating': 9, 'movie': {'ids': {'tmdb': 606}}},
        ]
        ratings_shows = [
            {'type': 'show', 'rating': 8, 'show': {'ids': {'tmdb': 707}}},
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))
            archive.writestr('watched-movies-1.json', json.dumps(watched_movies))
            archive.writestr('lists-watchlist.json', json.dumps(watchlist))
            archive.writestr('ratings-movies-1.json', json.dumps(ratings_movies))
            archive.writestr('ratings-shows.json', json.dumps(ratings_shows))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.total_items, 7)
        self.assertEqual(job.processed_items, 7)

        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=101).exists())
        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=202,
                season_number=2,
                episode_number=3,
            ).exists()
        )
        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=303).exists())

        self.assertTrue(Watchlist.objects.filter(user=self.user, media_type='movie', tmdb_id=404).exists())
        self.assertTrue(Watchlist.objects.filter(user=self.user, media_type='tv', tmdb_id=505).exists())

        self.assertTrue(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=606, score=9).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='tv', tmdb_id=707, score=8).exists())

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_zip_import_supports_watchlist_items_wrapper(self, mock_sync_movie, mock_sync_tv_show):
        watchlist_wrapped = {
            'items': [
                {'type': 'movie', 'movie': {'ids': {'tmdb': 1404}}},
                {'type': 'show', 'show': {'ids': {'tmdb': 1505}}},
            ]
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('lists-watchlist.json', json.dumps(watchlist_wrapped))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.metadata.get('summary', {}).get('watchlist'), 2)

        self.assertTrue(Watchlist.objects.filter(user=self.user, media_type='movie', tmdb_id=1404).exists())
        self.assertTrue(Watchlist.objects.filter(user=self.user, media_type='tv', tmdb_id=1505).exists())
        self.assertTrue(mock_sync_movie.called)
        self.assertTrue(mock_sync_tv_show.called)

    @patch('tracking.tasks.tmdb.sync_tv_show')
    def test_zip_import_processes_all_files_and_reports_unsupported(self, mock_sync_tv_show):
        watched_history = [
            {
                'type': 'movie',
                'watched_at': '2026-07-01T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 101}},
            },
        ]
        watched_shows = [
            {
                'show': {'ids': {'tmdb': 505}},
                'last_watched_at': '2026-07-01T10:00:00.000Z',
            },
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))
            archive.writestr('watched-shows.json', json.dumps(watched_shows))
            archive.writestr('user-profile.json', json.dumps({'username': 'demo'}))
            archive.writestr('notes-movies.json', json.dumps([]))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.total_items, 3)
        self.assertEqual(job.processed_items, 3)
        self.assertGreaterEqual(job.metadata.get('unsupported_files', 0), 2)
        self.assertGreaterEqual(job.metadata.get('unsupported_records', 0), 1)
        self.assertEqual(job.metadata.get('files_failed'), 0)
        self.assertGreaterEqual(job.metadata.get('records_imported', 0), 2)
        self.assertTrue(mock_sync_tv_show.called)

    @patch('tracking.tasks.tmdb.sync_season')
    def test_zip_import_syncs_season_metadata_for_episode_history(self, mock_sync_season):
        TVShow.objects.create(tmdb_id=202, name='Existing Show')
        watched_history = [
            {
                'type': 'episode',
                'watched_at': '2026-07-02T10:00:00.000Z',
                'episode': {'season': 2, 'number': 3},
                'show': {'ids': {'tmdb': 202}},
            },
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        self.assertTrue(mock_sync_season.called)

    def test_zip_import_maps_hidden_progress_to_dropped_show_status(self):
        hidden_progress = [
            {
                'type': 'show',
                'hidden_at': '2026-07-01T10:00:00.000Z',
                'show': {'ids': {'tmdb': 9090}},
            }
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hidden-progress-watched.json', json.dumps(hidden_progress))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=9090,
                season_number__isnull=True,
                episode_number__isnull=True,
                status='dropped',
            ).exists()
        )

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_local_import_syncs_metadata_for_items(self, mock_sync_movie, mock_sync_tv_show):
        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 111, 'status': 'watched'},
                {'media_type': 'episode', 'tmdb_id': 222, 'season_number': 1, 'episode_number': 1, 'status': 'watched'},
            ],
            'watchlist': [
                {'media_type': 'tv', 'tmdb_id': 333},
            ],
            'ratings': [
                {'media_type': 'movie', 'tmdb_id': 444, 'score': 8},
            ],
        }
        file_obj = SimpleUploadedFile('import.json', json.dumps(payload).encode('utf-8'), content_type='application/json')
        response = self.client.post('/api/tracking/data/import/?format=json&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        self.assertTrue(mock_sync_movie.called)
        self.assertTrue(mock_sync_tv_show.called)

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_local_import_skips_metadata_fetch_when_already_present(self, mock_sync_movie, mock_sync_tv_show):
        Movie.objects.create(tmdb_id=111, title='Existing movie')
        TVShow.objects.create(tmdb_id=333, name='Existing show')

        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 111, 'status': 'watched'},
            ],
            'watchlist': [
                {'media_type': 'tv', 'tmdb_id': 333},
            ],
            'ratings': [],
        }
        file_obj = SimpleUploadedFile('import.json', json.dumps(payload).encode('utf-8'), content_type='application/json')
        response = self.client.post('/api/tracking/data/import/?format=json&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import import_user_data
        import_user_data(response.data['id'])

        mock_sync_movie.assert_not_called()
        mock_sync_tv_show.assert_not_called()


class SystemTaskTests(TestCase):
    @patch('tracking.tasks.system.tmdb.sync_season')
    @patch('tracking.tasks.system.tmdb.sync_tv_show')
    @patch('tracking.tasks.system.tmdb.sync_movie')
    @patch('tracking.tasks.system.tmdb.get_tv_changes')
    @patch('tracking.tasks.system.tmdb.get_movie_changes')
    def test_sync_tmdb_changed_items_syncs_only_local_and_all_seasons(
        self,
        mock_get_movie_changes,
        mock_get_tv_changes,
        mock_sync_movie,
        mock_sync_tv_show,
        mock_sync_season,
    ):
        Movie.objects.create(tmdb_id=11, title='Local movie')
        show = TVShow.objects.create(tmdb_id=22, name='Local show', number_of_seasons=2)
        Season.objects.create(show=show, tmdb_id=2200, season_number=0, name='Specials')

        mock_get_movie_changes.side_effect = [
            {'results': [{'id': 11}, {'id': 999}], 'total_pages': 2},
            {'results': [{'id': 888}], 'total_pages': 2},
        ]
        mock_get_tv_changes.return_value = {
            'results': [{'id': 22}, {'id': 777}],
            'total_pages': 1,
        }
        mock_sync_tv_show.return_value = show

        from tracking.tasks.system import sync_tmdb_changed_items

        result = sync_tmdb_changed_items()

        self.assertEqual(result['movie_changed_total'], 3)
        self.assertEqual(result['tv_changed_total'], 2)
        self.assertEqual(result['local_movies_matched'], 1)
        self.assertEqual(result['local_tv_matched'], 1)
        self.assertEqual(result['movies_synced'], 1)
        self.assertEqual(result['tv_synced'], 1)
        self.assertEqual(result['seasons_synced'], 3)

        mock_sync_movie.assert_called_once_with(11)
        mock_sync_tv_show.assert_called_once_with(22)
        self.assertEqual(mock_sync_season.call_count, 3)
        synced_seasons = sorted(call.args[1] for call in mock_sync_season.call_args_list)
        self.assertEqual(synced_seasons, [0, 1, 2])

        self.assertEqual(mock_get_movie_changes.call_count, 2)
        self.assertEqual(mock_get_tv_changes.call_count, 1)
        for call in mock_get_movie_changes.call_args_list:
            self.assertFalse(call.kwargs['use_cache'])
        for call in mock_get_tv_changes.call_args_list:
            self.assertFalse(call.kwargs['use_cache'])

    @patch('tracking.tasks.system.tmdb.sync_movie')
    @patch('tracking.tasks.system.tmdb.get_tv_changes')
    @patch('tracking.tasks.system.tmdb.get_movie_changes')
    def test_sync_tmdb_changed_items_tracks_failures(self, mock_get_movie_changes, mock_get_tv_changes, mock_sync_movie):
        Movie.objects.create(tmdb_id=11, title='Movie A')
        Movie.objects.create(tmdb_id=12, title='Movie B')

        mock_get_movie_changes.return_value = {
            'results': [{'id': 11}, {'id': 12}],
            'total_pages': 1,
        }
        mock_get_tv_changes.return_value = {'results': [], 'total_pages': 1}
        mock_sync_movie.side_effect = [Exception('boom'), None]

        from tracking.tasks.system import sync_tmdb_changed_items

        result = sync_tmdb_changed_items()

        self.assertEqual(result['movies_synced'], 1)
        self.assertEqual(result['movie_failures'], 1)
        self.assertEqual(result['tv_synced'], 0)

    def test_celery_beat_schedule_has_daily_tmdb_sync(self):
        schedule_config = settings.CELERY_BEAT_SCHEDULE['tracking-sync-tmdb-changed-items-daily']

        self.assertEqual(schedule_config['task'], 'tracking.sync_tmdb_changed_items')
        self.assertIsInstance(schedule_config['schedule'], crontab)
        self.assertIn(schedule_config['schedule']._orig_hour, (4, '4'))
        self.assertIn(schedule_config['schedule']._orig_minute, (0, '0'))


class SyncTmdbChangedItemsCommandTests(TestCase):
    @patch('tracking.management.commands.sync_tmdb_changed_items.sync_tmdb_changed_items_for_window')
    @patch('tracking.management.commands.sync_tmdb_changed_items.timezone.localdate')
    def test_command_uses_default_window(self, mock_localdate, mock_sync):
        mock_localdate.return_value = timezone.datetime(2026, 8, 17).date()
        mock_sync.return_value = {'ok': 1}

        out = io.StringIO()
        call_command('sync_tmdb_changed_items', stdout=out)

        self.assertEqual(out.getvalue().strip(), '{"ok": 1}')
        mock_sync.assert_called_once_with(
            timezone.datetime(2026, 8, 16).date(),
            timezone.datetime(2026, 8, 17).date(),
        )

    @patch('tracking.management.commands.sync_tmdb_changed_items.sync_tmdb_changed_items_for_window')
    def test_command_accepts_custom_window(self, mock_sync):
        mock_sync.return_value = {'movies_synced': 2}

        out = io.StringIO()
        call_command(
            'sync_tmdb_changed_items',
            '--start-date=2026-08-01',
            '--end-date=2026-08-10',
            stdout=out,
        )

        mock_sync.assert_called_once_with(
            timezone.datetime(2026, 8, 1).date(),
            timezone.datetime(2026, 8, 10).date(),
        )

    def test_command_rejects_invalid_date(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-13-01')

    def test_command_rejects_start_after_end(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-08-10', '--end-date=2026-08-01')

    def test_command_rejects_window_longer_than_14_days(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-08-01', '--end-date=2026-08-20')
