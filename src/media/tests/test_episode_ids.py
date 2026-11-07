from unittest.mock import patch

import pytest

from media.episode_ids import resolve_episode_external_ids
from media.models import Episode, Season, TVShow
from media.tmdb import TMDBService

REF = (7778, 1, 2)


@pytest.fixture
def episode(db):
    show = TVShow.objects.create(tmdb_id=7778, name='Episode IDs')
    season = Season.objects.create(show=show, season_number=1, tmdb_id=1)
    return Episode.objects.create(season=season, episode_number=2, tmdb_id=2, name='E2', external_ids={'tvmaze_id': 4953})


@pytest.fixture
def fetch():
    with patch('media.episode_ids.tmdb.get_episode_external_ids') as mock:
        mock.return_value = {'tvdb_id': 321, 'imdb_id': 'tt1', 'wikidata_id': 'Q1', 'tvrage_id': None}
        yield mock


class TestResolveEpisodeExternalIds:
    def test_fetched_ids_are_stored_next_to_the_existing_ones(self, episode, fetch):
        ids = resolve_episode_external_ids([REF], required=('tvdb_id',))

        assert ids == {REF: {'tvmaze_id': 4953, 'tvdb_id': 321, 'imdb_id': 'tt1'}}
        episode.refresh_from_db()
        assert episode.external_ids == {'tvmaze_id': 4953, 'tvdb_id': 321, 'imdb_id': 'tt1'}

    def test_stored_ids_that_cover_the_required_keys_need_no_lookup(self, episode, fetch):
        episode.external_ids['tvdb_id'] = 321
        episode.save()

        ids = resolve_episode_external_ids([REF], required=('tvdb_id',))

        assert ids[REF]['tvdb_id'] == 321
        fetch.assert_not_called()

    def test_each_episode_is_fetched_once_with_the_given_cache_mode(self, episode, fetch):
        resolve_episode_external_ids([REF, REF], required=('tvdb_id',), use_cache=False)

        fetch.assert_called_once_with(*REF, use_cache=False)

    def test_an_empty_response_stores_nothing(self, episode, fetch):
        fetch.return_value = {'tvdb_id': None, 'imdb_id': None}

        ids = resolve_episode_external_ids([REF], required=('tvdb_id',))

        assert ids == {REF: {'tvmaze_id': 4953}}
        episode.refresh_from_db()
        assert episode.external_ids == {'tvmaze_id': 4953}

    def test_a_failed_lookup_returns_the_stored_ids(self, episode, fetch):
        fetch.side_effect = Exception('offline')

        ids = resolve_episode_external_ids([REF, (7778, 1, 9)], required=('tvdb_id',))

        assert ids == {REF: {'tvmaze_id': 4953}, (7778, 1, 9): {}}

    def test_an_episode_without_a_local_row_is_returned_but_not_stored(self, db, fetch):
        ids = resolve_episode_external_ids([REF], required=('tvdb_id',))

        assert ids == {REF: {'tvdb_id': 321, 'imdb_id': 'tt1'}}
        assert not Episode.objects.exists()

    def test_no_refs_make_no_lookups(self, db, fetch):
        assert resolve_episode_external_ids([], required=('tvdb_id',)) == {}
        fetch.assert_not_called()


class TestSyncKeepsStoredIds:
    def test_a_sync_payload_without_external_ids_keeps_the_stored_ones(self, episode):
        episode.external_ids['tvdb_id'] = 321

        defaults = TMDBService._episode_defaults({'id': 2, 'name': 'E2'}, episode)

        assert defaults['external_ids'] == {'tvmaze_id': 4953, 'tvdb_id': 321}
