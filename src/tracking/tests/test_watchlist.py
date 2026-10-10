from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Episode, Genre, Movie, Season, TVShow
from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class WatchlistTests(BaseTestCase):
    def test_add_to_watchlist(self):
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 201)

    @patch('media.tmdb.tmdb.sync_movie')
    def test_add_to_watchlist_syncs_movie_metadata(self, mock_sync_movie):
        mock_sync_movie.return_value = None
        data = {'media_type': 'movie', 'tmdb_id': 124}

        response = self.client.post('/api/tracking/watchlist/', data)

        self.assertEqual(response.status_code, 201)
        mock_sync_movie.assert_called_once_with(124)

    @patch('media.tmdb.tmdb.sync_tv_show')
    def test_add_to_watchlist_syncs_tv_metadata(self, mock_sync_tv_show):
        mock_sync_tv_show.return_value = None
        data = {'media_type': 'tv', 'tmdb_id': 457}

        response = self.client.post('/api/tracking/watchlist/', data)

        self.assertEqual(response.status_code, 201)
        mock_sync_tv_show.assert_called_once_with(457)

    @patch('media.tmdb.tmdb.sync_tv_show')
    @patch('media.tmdb.tmdb.sync_movie')
    def test_add_to_watchlist_skips_sync_for_locally_stored_media(self, mock_sync_movie, mock_sync_tv_show):
        Movie.objects.create(tmdb_id=125, title='Stored Movie')
        TVShow.objects.create(tmdb_id=458, name='Stored Show')

        for payload in ({'media_type': 'movie', 'tmdb_id': 125}, {'media_type': 'tv', 'tmdb_id': 458}):
            self.assertEqual(self.client.post('/api/tracking/watchlist/', payload).status_code, 201)

        mock_sync_movie.assert_not_called()
        mock_sync_tv_show.assert_not_called()

    def test_block_watched_content_to_watchlist(self):
        WatchEntry.objects.create(
            user=self.user, media_type='movie', tmdb_id=123,
            watched_at=timezone.now()
        )
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_block_show_with_watched_episodes(self):
        show = TVShow.objects.create(tmdb_id=456, name='Watched Show')
        season = Season.objects.create(show=show, tmdb_id=4561, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=45611, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1))
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=456,
            season_number=1, episode_number=1
        )
        data = {'media_type': 'tv', 'tmdb_id': 456}
        response = self.client.post('/api/tracking/watchlist/', data)
        self.assertEqual(response.status_code, 400)

    def test_allow_show_without_watched_episodes(self):
        TVShow.objects.create(tmdb_id=789, name='Show 789', status='Ended')
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
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=1101, status='plan_to_watch', status_changed_at=timezone.now())

        response = self.client.get('/api/tracking/watchlist/?media_type=movie')
        self.assertEqual(response.status_code, 200)

        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['tmdb_id'], 1101)
        self.assertEqual(entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(str(entry['release_date']), '2024-05-01')

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
        )
        Episode.objects.create(season=season, tmdb_id=32021, episode_number=1, name='Episode 1', runtime=45)
        Episode.objects.create(season=season, tmdb_id=32022, episode_number=2, name='Episode 2', runtime=50)
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=2202, status='plan_to_watch', status_changed_at=timezone.now())

        response = self.client.get('/api/tracking/watchlist/?media_type=tv')
        self.assertEqual(response.status_code, 200)

        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['tmdb_id'], 2202)
        self.assertEqual(entry['user_status']['status'], 'plan_to_watch')
        self.assertEqual(str(entry['release_date']), '2023-08-10')

    def test_watchlist_list_filters_genres(self):
        drama = Genre.objects.create(tmdb_id=901, name='Drama')
        comedy = Genre.objects.create(tmdb_id=902, name='Comedy')

        movie = Movie.objects.create(tmdb_id=2301, title='Drama Movie')
        movie.genres.add(drama)

        show = TVShow.objects.create(tmdb_id=2302, name='Comedy Show')
        show.genres.add(comedy)

        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=2301, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=2302, status='plan_to_watch', status_changed_at=timezone.now())

        filtered = self.client.get('/api/tracking/watchlist/?genres=Drama')
        self.assertEqual(filtered.status_code, 200)
        entries = filtered.data.get('results', filtered.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['tmdb_id'], 2301)

    def test_watchlist_sort_uses_title_as_secondary_tiebreaker(self):
        Movie.objects.create(tmdb_id=3001, title='Beta Movie')
        Movie.objects.create(tmdb_id=3002, title='Alpha Movie')
        first = UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=3001, status='plan_to_watch', status_changed_at=timezone.now())
        second = UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=3002, status='plan_to_watch', status_changed_at=timezone.now())

        shared_added_at = timezone.now()
        UserMediaStatus.objects.filter(id__in=[first.id, second.id]).update(status_changed_at=shared_added_at)

        response = self.client.get('/api/tracking/watchlist/?media_type=movie&sort=added_at&direction=asc')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual([entry['tmdb_id'] for entry in entries], [3002, 3001])


    def test_watchlist_missing_rating_excludes_plan_to_watch(self):
        Movie.objects.create(tmdb_id=3301, title='Plan Movie')
        TVShow.objects.create(tmdb_id=3302, name='Plan Show')
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=3301, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=3302, status='plan_to_watch', status_changed_at=timezone.now())

        response = self.client.get('/api/tracking/watchlist/?missing_rating=true')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(entries, [])
