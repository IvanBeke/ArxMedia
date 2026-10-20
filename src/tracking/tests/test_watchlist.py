from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Genre
from media.tests.factories import EpisodeFactory, MovieFactory, SeasonFactory, TVShowFactory
from tracking.models import (
    UserMediaStatus,
)
from tracking.tests.factories import EpisodeWatchEntryFactory, UserMediaStatusFactory, WatchEntryFactory

User = get_user_model()


pytestmark = pytest.mark.django_db

class WatchlistTests:
    def test_add_to_watchlist(self, user, auth_client, user2, tmdb_noop):
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = auth_client.post('/api/tracking/watchlist/', data)
        assert response.status_code == 201

    def test_add_to_watchlist_syncs_movie_metadata(self, mocker, user, auth_client, user2, tmdb_noop):
        mock_sync_movie = mocker.patch('media.tmdb.tmdb.sync_movie')
        mock_sync_movie.return_value = None
        data = {'media_type': 'movie', 'tmdb_id': 124}

        response = auth_client.post('/api/tracking/watchlist/', data)

        assert response.status_code == 201
        mock_sync_movie.assert_called_once_with(124)

    def test_add_to_watchlist_syncs_tv_metadata(self, mocker, user, auth_client, user2, tmdb_noop):
        mock_sync_tv_show = mocker.patch('media.tmdb.tmdb.sync_tv_show')
        mock_sync_tv_show.return_value = None
        data = {'media_type': 'tv', 'tmdb_id': 457}

        response = auth_client.post('/api/tracking/watchlist/', data)

        assert response.status_code == 201
        mock_sync_tv_show.assert_called_once_with(457)

    def test_add_to_watchlist_skips_sync_for_locally_stored_media(self, mocker, user, auth_client, user2, tmdb_noop):
        mock_sync_movie = mocker.patch('media.tmdb.tmdb.sync_movie')
        mock_sync_tv_show = mocker.patch('media.tmdb.tmdb.sync_tv_show')
        MovieFactory(tmdb_id=125, title='Stored Movie')
        TVShowFactory(tmdb_id=458, name='Stored Show')

        for payload in ({'media_type': 'movie', 'tmdb_id': 125}, {'media_type': 'tv', 'tmdb_id': 458}):
            assert auth_client.post('/api/tracking/watchlist/', payload).status_code == 201

        mock_sync_movie.assert_not_called()
        mock_sync_tv_show.assert_not_called()

    def test_block_watched_content_to_watchlist(self, user, auth_client, user2, tmdb_noop):
        WatchEntryFactory(user=user, tmdb_id=123, watched_at=timezone.now())
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = auth_client.post('/api/tracking/watchlist/', data)
        assert response.status_code == 400

    def test_block_show_with_watched_episodes(self, user, auth_client, user2, tmdb_noop):
        show = TVShowFactory(tmdb_id=456, name='Watched Show')
        season = SeasonFactory(show=show, tmdb_id=4561, season_number=1, name='Season 1')
        EpisodeFactory(season=season, tmdb_id=45611, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1))
        EpisodeWatchEntryFactory(user=user, tmdb_id=456, season_number=1, episode_number=1)
        data = {'media_type': 'tv', 'tmdb_id': 456}
        response = auth_client.post('/api/tracking/watchlist/', data)
        assert response.status_code == 400

    def test_allow_show_without_watched_episodes(self, user, auth_client, user2, tmdb_noop):
        TVShowFactory(tmdb_id=789, name='Show 789', status='Ended')
        data = {'media_type': 'tv', 'tmdb_id': 789}
        response = auth_client.post('/api/tracking/watchlist/', data)
        assert response.status_code == 201

    def test_watchlist_list_includes_movie_user_status_and_dates(self, user, auth_client, user2, tmdb_noop):
        MovieFactory(
            tmdb_id=1101,
            title='Movie For Watchlist',
            release_date=timezone.datetime(2024, 5, 1).date(),
            runtime=127,
        )
        UserMediaStatusFactory(user=user, tmdb_id=1101, status_changed_at=timezone.now())

        response = auth_client.get('/api/tracking/watchlist/?media_type=movie')
        assert response.status_code == 200

        entries = response.data.get('results', response.data)
        assert len(entries) == 1
        entry = entries[0]
        assert entry['tmdb_id'] == 1101
        assert entry['user_status']['status'] == 'plan_to_watch'
        assert str(entry['release_date']) == '2024-05-01'

    def test_watchlist_list_includes_tv_plan_to_watch_status(self, user, auth_client, user2, tmdb_noop):
        show = TVShowFactory(
            tmdb_id=2202,
            name='Show For Watchlist',
            first_air_date=timezone.datetime(2023, 8, 10).date(),
            episode_runtime=46,
            number_of_episodes=12,
        )
        season = SeasonFactory(
            show=show,
            tmdb_id=3202,
            season_number=1,
            name='Season 1',
        )
        EpisodeFactory(season=season, tmdb_id=32021, episode_number=1, name='Episode 1', runtime=45)
        EpisodeFactory(season=season, tmdb_id=32022, episode_number=2, name='Episode 2', runtime=50)
        UserMediaStatusFactory(user=user, media_type='tv', tmdb_id=2202, status_changed_at=timezone.now())

        response = auth_client.get('/api/tracking/watchlist/?media_type=tv')
        assert response.status_code == 200

        entries = response.data.get('results', response.data)
        assert len(entries) == 1
        entry = entries[0]
        assert entry['tmdb_id'] == 2202
        assert entry['user_status']['status'] == 'plan_to_watch'
        assert str(entry['release_date']) == '2023-08-10'

    def test_watchlist_total_runtime_falls_back_to_show_runtime(self, user, auth_client, user2, tmdb_noop):
        show = TVShowFactory(tmdb_id=2203, name='Fallback Runtime Watchlist Show', episode_runtime=46)
        season = SeasonFactory(show=show, tmdb_id=3203, season_number=1, name='Season 1')
        EpisodeFactory(season=season, tmdb_id=32031, episode_number=1, name='Episode 1', runtime=None)
        EpisodeFactory(season=season, tmdb_id=32032, episode_number=2, name='Episode 2', runtime=None)
        UserMediaStatusFactory(user=user, media_type='tv', tmdb_id=2203, status_changed_at=timezone.now())

        response = auth_client.get('/api/tracking/watchlist/?media_type=tv')

        assert response.status_code == 200
        assert response.data['total_runtime_minutes'] == 92

    def test_watchlist_list_filters_genres(self, user, auth_client, user2, tmdb_noop):
        drama = Genre.objects.create(tmdb_id=901, name='Drama')
        comedy = Genre.objects.create(tmdb_id=902, name='Comedy')

        movie = MovieFactory(tmdb_id=2301, title='Drama Movie')
        movie.genres.add(drama)

        show = TVShowFactory(tmdb_id=2302, name='Comedy Show')
        show.genres.add(comedy)

        UserMediaStatusFactory(user=user, tmdb_id=2301, status_changed_at=timezone.now())
        UserMediaStatusFactory(user=user, media_type='tv', tmdb_id=2302, status_changed_at=timezone.now())

        filtered = auth_client.get('/api/tracking/watchlist/?genres=Drama')
        assert filtered.status_code == 200
        entries = filtered.data.get('results', filtered.data)
        assert len(entries) == 1
        assert entries[0]['tmdb_id'] == 2301

    def test_watchlist_sort_uses_title_as_secondary_tiebreaker(self, user, auth_client, user2, tmdb_noop):
        MovieFactory(tmdb_id=3001, title='Beta Movie')
        MovieFactory(tmdb_id=3002, title='Alpha Movie')
        first = UserMediaStatusFactory(user=user, tmdb_id=3001, status_changed_at=timezone.now())
        second = UserMediaStatusFactory(user=user, tmdb_id=3002, status_changed_at=timezone.now())

        shared_added_at = timezone.now()
        UserMediaStatus.objects.filter(id__in=[first.id, second.id]).update(status_changed_at=shared_added_at)

        response = auth_client.get('/api/tracking/watchlist/?media_type=movie&sort=added_at&direction=asc')
        assert response.status_code == 200
        entries = response.data.get('results', response.data)
        assert [entry['tmdb_id'] for entry in entries] == [3002, 3001]


    def test_watchlist_missing_rating_excludes_plan_to_watch(self, user, auth_client, user2, tmdb_noop):
        MovieFactory(tmdb_id=3301, title='Plan Movie')
        TVShowFactory(tmdb_id=3302, name='Plan Show')
        UserMediaStatusFactory(user=user, tmdb_id=3301, status_changed_at=timezone.now())
        UserMediaStatusFactory(user=user, media_type='tv', tmdb_id=3302, status_changed_at=timezone.now())

        response = auth_client.get('/api/tracking/watchlist/?missing_rating=true')
        assert response.status_code == 200
        entries = response.data.get('results', response.data)
        assert entries == []
