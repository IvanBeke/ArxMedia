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
from media.models import Episode, Genre, Movie, Season, TVShow
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from social.models import Follow

from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    UserTvShowStatus,
    WatchEntry,
    Watchlist,
)
from tracking.status_annotations import annotate_season_user_status
from tracking.status_sync import refresh_all_statuses_for_show

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
        data = {'media_type': 'movie', 'tmdb_id': 123}
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
        data = {'media_type': 'movie', 'tmdb_id': 999}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Watchlist.objects.count(), 0)

    def test_drop_show(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=789,
            season_number=1, episode_number=1
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
            ).count(),
            1,
        )
        dropped_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=789)
        self.assertEqual(dropped_status.status, 'dropped')
        self.assertIsNotNone(dropped_status.dropped_at)

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
            watched_at=older,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=600,
            watched_at=newer,
        )

        response = self.client.get('/api/tracking/history/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 600)

    def test_history_episode_includes_runtime(self):
        show = TVShow.objects.create(tmdb_id=5001, name='Runtime Show', episode_runtime=41)
        season = Season.objects.create(
            show=show,
            tmdb_id=50010,
            season_number=1,
            name='Season 1',
            episode_count=1,
        )
        Episode.objects.create(
            season=season,
            tmdb_id=500101,
            episode_number=1,
            name='Pilot',
            runtime=44,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=5001,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['runtime'], 44)

    def test_history_list_filters_media_type(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=700,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=701,
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
            watched_at=newer,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=801,
            watched_at=older,
        )

        response = self.client.get('/api/tracking/history/?order=oldest')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 801)
        self.assertEqual(data[1]['tmdb_id'], 800)

    def test_history_episode_uses_episode_title_and_show_name(self):
        show = TVShow.objects.create(tmdb_id=1900, name='The Example Show')
        season = Season.objects.create(show=show, tmdb_id=2901, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=3901, episode_number=3, name='Pilot Episode')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=1900,
            season_number=1,
            episode_number=3,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['title'], 'Pilot Episode')
        self.assertEqual(data[0]['show_name'], 'The Example Show')

    def test_history_movie_includes_user_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=2101,
            watched_at=timezone.now(),
        )
        Rating.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=2101,
            score=9,
        )

        response = self.client.get('/api/tracking/history/?media_type=movie')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['tmdb_id'], 2101)
        self.assertEqual(data[0]['rating'], 9)

    def test_history_episode_includes_show_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2102,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )
        Rating.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=2102,
            score=8,
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['tmdb_id'], 2102)
        self.assertEqual(data[0]['rating'], 8)


class RatingTests(BaseTestCase):
    def test_create_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=123,
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
            watched_at=timezone.now()
        )
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_block_show_with_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=456,
            season_number=1, episode_number=1
        )
        data = {'media_type': 'tv', 'tmdb_id': 456}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_allow_show_without_watched_episodes(self):
        UserTvShowStatus.objects.create(
            user=self.user,
            tmdb_id=789,
            status='plan_to_watch',
            watched_episodes=0,
        )
        data = {'media_type': 'tv', 'tmdb_id': 789}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 201)

    def test_watchlist_list_includes_movie_user_status_and_dates(self):
        Movie.objects.create(
            tmdb_id=1101,
            title='Movie For Watchlist',
            release_date=timezone.datetime(2024, 5, 1).date(),
            runtime=127,
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
        self.assertEqual(entry['runtime'], 127)

    def test_watchlist_list_includes_tv_plan_to_watch_status(self):
        show = TVShow.objects.create(
            tmdb_id=2202,
            name='Show For Watchlist',
            first_air_date=timezone.datetime(2023, 8, 10).date(),
            episode_runtime=46,
            number_of_episodes=12,
        )
        season = Season.objects.create(
            show=show,
            tmdb_id=3202,
            season_number=1,
            name='Season 1',
            episode_count=2,
        )
        Episode.objects.create(season=season, tmdb_id=32021, episode_number=1, name='Episode 1', runtime=45)
        Episode.objects.create(season=season, tmdb_id=32022, episode_number=2, name='Episode 2', runtime=50)
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
        self.assertEqual(entry['runtime'], 95)

    def test_watchlist_list_filters_genres(self):
        drama = Genre.objects.create(tmdb_id=901, name='Drama')
        comedy = Genre.objects.create(tmdb_id=902, name='Comedy')

        movie = Movie.objects.create(tmdb_id=2301, title='Drama Movie')
        movie.genres.add(drama)

        show = TVShow.objects.create(tmdb_id=2302, name='Comedy Show')
        show.genres.add(comedy)

        Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=2301)
        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=2302)

        filtered = self.client.get('/api/tracking/watchlist/?genres=Drama')
        self.assertEqual(filtered.status_code, 200)
        entries = filtered.data.get('results', filtered.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['tmdb_id'], 2301)

    def test_watchlist_sort_uses_title_as_secondary_tiebreaker(self):
        Movie.objects.create(tmdb_id=3001, title='Beta Movie')
        Movie.objects.create(tmdb_id=3002, title='Alpha Movie')
        first = Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=3001)
        second = Watchlist.objects.create(user=self.user, media_type='movie', tmdb_id=3002)

        shared_added_at = timezone.now()
        Watchlist.objects.filter(id__in=[first.id, second.id]).update(added_at=shared_added_at)

        response = self.client.get('/api/tracking/watchlist/?media_type=movie&sort=added_at&direction=asc')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual([entry['tmdb_id'] for entry in entries], [3002, 3001])


class EpisodeTests(BaseTestCase):
    def test_mark_episode_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/mark/', data)
        self.assertEqual(response.status_code, 201)

    def test_unmark_episode_watched(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/unmark/', data)
        self.assertEqual(response.status_code, 200)

    def test_get_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
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

    def test_unmark_show_watched(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=2
        )
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=456,
            season_number=1, episode_number=1
        )
        WatchEntry.objects.create(
            user=self.user2, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )

        response = self.client.post('/api/tracking/shows/unmark/', {'tmdb_id': 123})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('unmarked'), 2)

        self.assertFalse(
            WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=123).exists()
        )
        self.assertTrue(
            WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=456).exists()
        )
        self.assertTrue(
            WatchEntry.objects.filter(user=self.user2, media_type='episode', tmdb_id=123).exists()
        )

    def test_unmark_show_watched_requires_tmdb_id(self):
        response = self.client.post('/api/tracking/shows/unmark/', {})
        self.assertEqual(response.status_code, 400)


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
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9200,
            season_number=1,
            episode_number=2,
        )

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=9200)
        season_status = annotate_season_user_status(
            self.user,
            [{'tmdb_id': 9200, 'season_number': 1}],
        )[(9200, 1)]
        self.assertEqual(show_status.status, 'watching')
        self.assertEqual(season_status['status'], 'watching')

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
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=9300,
            season_number=1,
            episode_number=2,
        )

        show_status = UserTvShowStatus.objects.get(user=self.user, tmdb_id=9300)
        season_status = annotate_season_user_status(
            self.user,
            [{'tmdb_id': 9300, 'season_number': 1}],
        )[(9300, 1)]
        self.assertEqual(show_status.status, 'watched')
        self.assertEqual(season_status['status'], 'watched')


class RefreshAllShowStatusesTests(BaseTestCase):
    @patch('tracking.tasks.system.refresh_show_status_for_user.delay')
    @patch('tracking.status_sync.refresh_show_status')
    def test_refreshes_current_user_sync_and_queues_remaining(self, mock_refresh_show_status, mock_delay):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=7770,
            season_number=1,
            episode_number=1,
        )
        UserTvShowStatus.objects.create(user=self.user2, tmdb_id=7770, status='watching')

        refresh_all_statuses_for_show(7770, current_user_id=self.user.id)

        mock_refresh_show_status.assert_called_once_with(self.user.id, 7770)
        mock_delay.assert_called_once_with(7770, self.user2.id)

    @patch('tracking.tasks.system.refresh_show_status_for_user.delay')
    @patch('tracking.status_sync.refresh_show_status')
    def test_no_logged_user_queues_all_candidates(self, mock_refresh_show_status, mock_delay):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=7771,
            season_number=1,
            episode_number=1,
        )
        UserTvShowStatus.objects.create(user=self.user2, tmdb_id=7771, status='watching')

        refresh_all_statuses_for_show(7771)

        mock_refresh_show_status.assert_not_called()
        self.assertEqual(mock_delay.call_count, 2)
        self.assertEqual(
            {tuple(call.args) for call in mock_delay.call_args_list},
            {(7771, self.user.id), (7771, self.user2.id)},
        )

    @patch('tracking.tasks.system.refresh_show_status_for_user.delay')
    @patch('tracking.status_sync.refresh_show_status')
    def test_watchlist_only_users_are_not_refreshed(self, mock_refresh_show_status, mock_delay):
        Watchlist.objects.create(user=self.user, media_type='tv', tmdb_id=7772)

        refresh_all_statuses_for_show(7772, current_user_id=self.user.id)

        mock_refresh_show_status.assert_not_called()
        mock_delay.assert_not_called()


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

    def test_up_next_includes_progress_and_remaining_runtime_fields(self):
        today = timezone.now().date()
        show = TVShow.objects.create(tmdb_id=777, name='Runtime Show')
        season = Season.objects.create(show=show, tmdb_id=7771, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=77711, episode_number=1, name='Episode 1', air_date=today - timedelta(days=5), runtime=20)
        Episode.objects.create(season=season, tmdb_id=77712, episode_number=2, name='Episode 2', air_date=today - timedelta(days=4), runtime=30)
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
        self.assertEqual(item['episodes_left'], 2)
        self.assertEqual(item['runtime_left_minutes'], 30)
        self.assertEqual(item['runtime_left_has_unknown'], True)
        self.assertEqual(item['progress_percent'], 25)

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
        UserTvShowStatus.objects.update_or_create(
            user=self.user,
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
        Episode.objects.create(season=season1, tmdb_id=300211, episode_number=1, name='Upcoming Episode', air_date=today + timedelta(days=2))

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
            status='Returning Series',
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
        UserTvShowStatus.objects.update_or_create(
            user=self.user,
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
        response = self.client.get('/api/tracking/progress/')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003})

    def test_progress_list_filters_missing_rating(self):
        response = self.client.get('/api/tracking/progress/?missing_rating=true')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertTrue(all(item['user_rating'] is None for item in items))
        self.assertEqual({item['tmdb_id'] for item in items}, {4001, 4003})

    def test_progress_list_filters_genres_multi(self):
        response = self.client.get('/api/tracking/progress/?genres=Drama&genres=Sci-Fi')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003})

    def test_progress_list_filters_status_and_search(self):
        response = self.client.get('/api/tracking/progress/?status=dropped&search=gamma')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['status'], 'dropped')
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_filters_user_status_multi_select(self):
        response = self.client.get('/api/tracking/progress/?status=watching&status=watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002})

    def test_progress_list_filters_provider_status_multi_select(self):
        response = self.client.get('/api/tracking/progress/?provider_status=Ended&provider_status=Returning%20Series')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        tmdb_ids = {item['tmdb_id'] for item in items}
        self.assertEqual(tmdb_ids, {4001, 4002, 4003})

    def test_progress_list_includes_available_provider_statuses(self):
        response = self.client.get('/api/tracking/progress/')
        self.assertEqual(response.status_code, 200)
        statuses = response.data.get('available_provider_statuses', [])
        self.assertEqual(statuses, ['Ended', 'Returning Series'])

    def test_progress_list_filters_watching_requires_episodes_left(self):
        response = self.client.get('/api/tracking/progress/?status=watching')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual([item['tmdb_id'] for item in items], [4001])
        self.assertTrue(all(item['episodes_left'] > 0 for item in items))

    def test_progress_list_filters_completed_by_full_progress(self):
        response = self.client.get('/api/tracking/progress/?status=watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual([item['tmdb_id'] for item in items], [4002])
        self.assertTrue(all(item['progress_percent'] == 100 for item in items))

    def test_progress_list_sorts_time_left(self):
        response = self.client.get('/api/tracking/progress/?sort=time_left')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_sorts_last_watched(self):
        response = self.client.get('/api/tracking/progress/?sort=last_watched')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4001)

    def test_progress_list_sorts_episodes_left(self):
        response = self.client.get('/api/tracking/progress/?sort=episodes_left')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(items[0]['tmdb_id'], 4003)

    def test_progress_list_filters_upcoming_and_new(self):
        response = self.client.get('/api/tracking/progress/?has_upcoming=true&is_new=true')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tmdb_id'], 4001)
        self.assertTrue(items[0]['has_upcoming_episode'])
        self.assertTrue(items[0]['is_new'])

    def test_progress_list_includes_total_watched_minutes(self):
        response = self.client.get('/api/tracking/progress/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_watched_minutes', response.data)
        self.assertEqual(response.data['total_watched_minutes'], 182)

    def test_progress_list_total_watched_minutes_respects_filters(self):
        response = self.client.get('/api/tracking/progress/?status=watched')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_watched_minutes', response.data)
        self.assertEqual(response.data['total_watched_minutes'], 110)

    def test_progress_list_includes_last_watched_episode_code_parts(self):
        response = self.client.get('/api/tracking/progress/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4001)
        self.assertEqual(item['last_watched_episode']['season_number'], 1)
        self.assertEqual(item['last_watched_episode']['episode_number'], 1)

    def test_progress_list_includes_started_at_from_oldest_watch_entry(self):
        response = self.client.get('/api/tracking/progress/?search=beta')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4002)
        self.assertTrue(str(item['started_at']).startswith('2026-01-08'))

    def test_progress_list_includes_next_episode_provider_rating_fields(self):
        response = self.client.get('/api/tracking/progress/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4001)
        self.assertEqual(item['next_episode']['vote_average'], 8.6)
        self.assertEqual(item['next_episode']['vote_count'], 210)

    def test_progress_list_includes_provider_show_status(self):
        response = self.client.get('/api/tracking/progress/?search=beta')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['tmdb_id'], 4002)
        self.assertEqual(item['provider_status'], 'Returning Series')

    def test_progress_list_includes_episode_runtime(self):
        response = self.client.get('/api/tracking/progress/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['episode_runtime'], 42)

    def test_progress_list_includes_number_of_seasons(self):
        response = self.client.get('/api/tracking/progress/?search=alpha')
        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['number_of_seasons'], 1)


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
        data = {'name': 'Updated List', 'privacy': 'private'}
        response = self.client.patch(f'/api/tracking/lists/{lst.id}/', data)
        self.assertEqual(response.status_code, 200)
        lst.refresh_from_db()
        self.assertEqual(lst.name, 'Updated List')

    def test_cannot_create_list_with_followers_privacy(self):
        response = self.client.post('/api/tracking/lists/', {
            'name': 'Legacy Privacy',
            'privacy': 'followers',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('privacy', response.data)

    def test_public_list_hidden_when_owner_account_is_private(self):
        self.user2.account_visibility = 'private'
        self.user2.save(update_fields=['account_visibility'])
        CustomList.objects.create(user=self.user2, name='Hidden Public', privacy='public')

        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

    def test_public_list_visible_to_mutual_friend_when_owner_friends_only(self):
        self.user2.account_visibility = 'friends_only'
        self.user2.save(update_fields=['account_visibility'])
        target = CustomList.objects.create(user=self.user2, name='Friends Public', privacy='public')

        not_friend = self.client.get('/api/tracking/lists/')
        self.assertEqual(not_friend.status_code, 200)
        self.assertEqual(len(not_friend.data['results']), 0)

        Follow.objects.create(follower=self.user, following=self.user2)
        Follow.objects.create(follower=self.user2, following=self.user)

        as_friend = self.client.get('/api/tracking/lists/')
        self.assertEqual(as_friend.status_code, 200)
        self.assertEqual(len(as_friend.data['results']), 1)
        self.assertEqual(as_friend.data['results'][0]['id'], target.id)

    def test_collaborator_can_access_private_list(self):
        private_list = CustomList.objects.create(user=self.user2, name='Private Collab', privacy='private')
        ListCollaborator.objects.create(custom_list=private_list, user=self.user)

        list_response = self.client.get('/api/tracking/lists/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data['results']), 1)
        self.assertEqual(list_response.data['results'][0]['id'], private_list.id)

        detail_response = self.client.get(f'/api/tracking/lists/{private_list.id}/')
        self.assertEqual(detail_response.status_code, 200)

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

    def test_list_detail_includes_items_payload(self):
        lst = CustomList.objects.create(user=self.user, name='Detail List')
        Movie.objects.create(tmdb_id=888, title='Detail Movie', runtime=99)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=888)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('items', response.data)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['tmdb_id'], 888)
        self.assertEqual(response.data['items'][0]['runtime'], 99)

    def test_list_items_includes_tv_runtime(self):
        lst = CustomList.objects.create(user=self.user, name='Runtime List')
        show = TVShow.objects.create(tmdb_id=9911, name='Runtime Show', episode_runtime=52, number_of_episodes=8)
        season = Season.objects.create(
            show=show,
            tmdb_id=99110,
            season_number=1,
            name='Runtime Season',
            episode_count=2,
        )
        Episode.objects.create(season=season, tmdb_id=991101, episode_number=1, name='Runtime Ep1', runtime=52)
        Episode.objects.create(season=season, tmdb_id=991102, episode_number=2, name='Runtime Ep2', runtime=48)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=9911)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(response.status_code, 200)
        items = response.data.get('results', response.data)
        self.assertEqual(items[0]['runtime'], 100)

    def test_duplicate_add_to_list_returns_validation_error(self):
        lst = CustomList.objects.create(user=self.user, name='Unique List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=222)

        response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 222})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'), 'Item is already in this list.')

    def test_list_items_title_sort_works(self):
        lst = CustomList.objects.create(user=self.user, name='Sort by title')
        Movie.objects.create(tmdb_id=7101, title='Zulu')
        Movie.objects.create(tmdb_id=7102, title='Alpha')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7101)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7102)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=title&direction=asc')
        self.assertEqual(response.status_code, 200)
        items = response.data.get('results', response.data)
        self.assertEqual([item['tmdb_id'] for item in items], [7102, 7101])

    def test_list_items_filter_genres(self):
        lst = CustomList.objects.create(user=self.user, name='Genre List')
        drama = Genre.objects.create(tmdb_id=911, name='Drama')
        thriller = Genre.objects.create(tmdb_id=912, name='Thriller')

        movie = Movie.objects.create(tmdb_id=7201, title='Drama Film')
        movie.genres.add(drama)
        show = TVShow.objects.create(tmdb_id=7202, name='Thriller Show')
        show.genres.add(thriller)

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7201)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7202)

        filtered = self.client.get(f'/api/tracking/lists/{lst.id}/items/?genres=Thriller')
        self.assertEqual(filtered.status_code, 200)
        items = filtered.data.get('results', filtered.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tmdb_id'], 7202)


class UserStatsTests(BaseTestCase):
    def test_stats_endpoint(self):
        response = self.client.get('/api/tracking/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('movies_watched', response.data)
        self.assertIn('episodes_watched', response.data)

    def test_stats_with_watched_movie(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123,
            watched_at=timezone.now()
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
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=10)
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
        self.assertEqual(response.data.get('source'), 'yamtrack')

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
            source='trakt',
            metadata={'total_items': 3, 'summary': {'watch_history': 1, 'watchlist': 1, 'ratings': 1}},
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
        self.assertEqual(job.import_mode, 'mirror_imported_set')
        mock_delay.assert_called_once_with(job.id)

    @patch('tracking.tasks.apply_yamtrack_csv_import.delay')
    def test_confirm_yamtrack_csv_starts_apply_task(self, mock_delay):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            source='yamtrack',
            metadata={
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
        self.assertEqual(job.import_mode, 'update_existing')
        mock_delay.assert_called_once_with(job.id)

    def test_confirm_mismatched_source_format_is_rejected(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            source='arxmedia',
            metadata={'total_items': 1},
        )
        response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'new_items'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('error_code'), 'IMPORT_SOURCE_FORMAT_MISMATCH')

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
            source='yamtrack',
            import_mode='new_items',
            metadata={'total_items': 5},
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
        self.assertEqual(episode_entry.watched_at.isoformat(), '2026-02-01T12:30:00+00:00')

        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=601).exists())
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

        from tracking.tasks import apply_trakt_zip_import, prepare_trakt_zip_import

        prepare_trakt_zip_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_trakt_zip_import(response.data['id'])

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

        from tracking.tasks import apply_trakt_zip_import, prepare_trakt_zip_import

        prepare_trakt_zip_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_trakt_zip_import(response.data['id'])

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

        from tracking.tasks import apply_trakt_zip_import, prepare_trakt_zip_import

        prepare_trakt_zip_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_trakt_zip_import(response.data['id'])

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

        from tracking.tasks import apply_trakt_zip_import, prepare_trakt_zip_import

        prepare_trakt_zip_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_trakt_zip_import(response.data['id'])

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

        from tracking.tasks import apply_trakt_zip_import, prepare_trakt_zip_import

        prepare_trakt_zip_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_trakt_zip_import(response.data['id'])

        self.assertTrue(
            UserTvShowStatus.objects.filter(
                user=self.user,
                tmdb_id=9090,
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

        from tracking.tasks import apply_arxmedia_json_import, prepare_arxmedia_json_import

        prepare_arxmedia_json_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_arxmedia_json_import(response.data['id'])

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

        from tracking.tasks import apply_arxmedia_json_import, prepare_arxmedia_json_import

        prepare_arxmedia_json_import(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        apply_arxmedia_json_import(response.data['id'])

        mock_sync_movie.assert_not_called()
        mock_sync_tv_show.assert_not_called()


class SystemTaskTests(TestCase):
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
    ):
        Movie.objects.create(tmdb_id=11, title='Local movie')
        show = TVShow.objects.create(tmdb_id=22, name='Local show', number_of_seasons=2)
        Season.objects.create(show=show, tmdb_id=2200, season_number=0, name='Specials')
        Season.objects.create(show=show, tmdb_id=2201, season_number=1, name='Season 1')
        Season.objects.create(show=show, tmdb_id=2202, season_number=2, name='Season 2')

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
        self.assertEqual(result['episode_credits_synced'], 0)
        self.assertEqual(result['episode_credit_failures'], 0)

        mock_sync_movie.assert_called_once_with(11)
        mock_sync_tv_show.assert_called_once_with(22)

        self.assertEqual(mock_get_movie_changes.call_count, 2)
        self.assertEqual(mock_get_tv_changes.call_count, 1)
        for call in mock_get_movie_changes.call_args_list:
            self.assertFalse(call.kwargs['use_cache'])
        for call in mock_get_tv_changes.call_args_list:
            self.assertFalse(call.kwargs['use_cache'])

    @patch('tracking.tasks.system.tmdb.sync_episode_credits')
    @patch('tracking.tasks.system.tmdb.sync_tv_show')
    @patch('tracking.tasks.system.tmdb.sync_movie')
    @patch('tracking.tasks.system.tmdb.get_tv_changes')
    @patch('tracking.tasks.system.tmdb.get_movie_changes')
    def test_sync_tmdb_changed_items_refreshes_episode_credits_for_changed_local_shows(
        self,
        mock_get_movie_changes,
        mock_get_tv_changes,
        mock_sync_movie,
        mock_sync_tv_show,
        mock_sync_episode_credits,
    ):
        show = TVShow.objects.create(tmdb_id=3333, name='Changed Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=33331, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=333311, episode_number=1, name='Episode 1')
        season.episodes.create(tmdb_id=333312, episode_number=2, name='Episode 2')

        mock_get_movie_changes.return_value = {'results': [], 'total_pages': 1}
        mock_get_tv_changes.return_value = {'results': [{'id': 3333}], 'total_pages': 1}
        mock_sync_tv_show.return_value = show

        from tracking.tasks.system import sync_tmdb_changed_items

        result = sync_tmdb_changed_items()

        self.assertEqual(result['tv_changed_total'], 1)
        self.assertEqual(result['local_tv_matched'], 1)
        self.assertEqual(result['episode_credits_synced'], 2)
        self.assertEqual(result['episode_credit_failures'], 0)
        self.assertEqual(mock_sync_episode_credits.call_count, 2)
        called_triplets = sorted((c.args[0], c.args[1], c.args[2]) for c in mock_sync_episode_credits.call_args_list)
        self.assertEqual(called_triplets, [(3333, 1, 1), (3333, 1, 2)])
        mock_sync_movie.assert_not_called()

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
