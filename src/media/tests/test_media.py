import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from media.http import response_cache_key
from media.models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow
from media.tmdb import _non_empty_defaults, tmdb
from media.tvmaze import TVMazeService, tvmaze
from tracking.models import Rating, UserMediaStatus, WatchEntry

User = get_user_model()


pytestmark = pytest.mark.django_db

class MediaTests:
    def test_tvmaze_normalizes_timezone_aware_broadcast_start(self):
        payload = TVMazeService.normalize_episode_from_tvmaze(
            {'network': {'country': {'timezone': 'America/New_York'}}},
            {'name': 'Pilot', 'airdate': '2026-01-01', 'airtime': '21:30', 'summary': 'A pilot'},
        )

        assert payload['broadcast_start'].isoformat() == '2026-01-01T21:30:00-05:00'

    def test_tvmaze_allows_null_channel_countries(self):
        show = {
            'network': {'country': None},
            'webChannel': {'country': None},
            'schedule': {'time': '21:30'},
        }

        payload = TVMazeService.normalize_episode_from_tvmaze(
            show,
            {'name': 'Pilot', 'airdate': '2026-01-01', 'airtime': '21:30'},
        )

        assert timezone.is_aware(payload['broadcast_start'])
        assert TVMazeService.parse_show_schedule_datetime(show, '2026-01-01') is not None

    def test_episode_air_time_is_derived_from_broadcast_start(self):
        show = TVShow.objects.create(tmdb_id=992, name='Air Time Show')
        episode = show.seasons.create(tmdb_id=9921, season_number=1, name='Season 1').episodes.create(
            tmdb_id=99211,
            episode_number=1,
            name='Episode 1',
            broadcast_start=timezone.make_aware(timezone.datetime(2026, 1, 1, 21, 30)),
        )

        assert episode.air_time == '21:30'
        assert episode.display_air_date.isoformat() == '2026-01-01T21:30:00+01:00'

    def test_episode_display_air_date_falls_back_to_air_date(self):
        show = TVShow.objects.create(tmdb_id=993, name='Air Date Fallback Show')
        episode = show.seasons.create(tmdb_id=9931, season_number=1, name='Season 1').episodes.create(
            tmdb_id=99311,
            episode_number=1,
            name='Episode 1',
            air_date='2026-01-02',
        )

        assert str(episode.display_air_date) == '2026-01-02'

    def test_episode_query_helpers_preserve_release_and_special_boundaries(self):
        show = TVShow.objects.create(tmdb_id=9940, name='Episode Query Show')
        regular = show.seasons.create(tmdb_id=9941, season_number=1, name='Season 1')
        specials = show.seasons.create(tmdb_id=9942, season_number=0, name='Specials')
        yesterday = timezone.localdate() - timedelta(days=1)
        tomorrow = timezone.localdate() + timedelta(days=1)
        released = regular.episodes.create(tmdb_id=99401, episode_number=1, name='Released', air_date=yesterday, runtime=40)
        upcoming = regular.episodes.create(tmdb_id=99402, episode_number=2, name='Upcoming', air_date=tomorrow)
        special = specials.episodes.create(tmdb_id=99403, episode_number=1, name='Special', air_date=yesterday)

        assert released in Episode.objects.released()
        assert upcoming not in Episode.objects.released()
        assert special not in Episode.objects.released()
        assert special in Episode.objects.released(include_specials=True)
        assert upcoming in Episode.objects.upcoming()
        assert special not in Episode.objects.upcoming()
        assert released in Episode.objects.regular()
        assert special in Episode.objects.specials()

    def test_tvmaze_falls_back_to_current_timezone_for_invalid_timezone(self):
        broadcast_start = TVMazeService.parse_air_datetime('2026-01-01', '21:30', 'invalid/zone')

        assert broadcast_start is not None
        assert timezone.is_aware(broadcast_start)

    def test_tvmaze_parses_show_schedule_for_episode_fallback(self):
        broadcast_start = TVMazeService.parse_show_schedule_datetime(
            {
                'schedule': {'time': '22:30'},
                'network': {'country': {'timezone': 'Asia/Tokyo'}},
            },
            '2026-09-09',
        )

        assert broadcast_start.isoformat() == '2026-09-09T22:30:00+09:00'

    def test_tvmaze_lookup_prefers_external_ids(self, mocker):
        mock_request = mocker.patch.object(TVMazeService, '_request')
        mock_request.return_value = {'id': 101, 'name': 'Matched Show'}

        result = TVMazeService().lookup_show(
            external_ids={'tvdb_id': 202, 'imdb_id': 'tt303', 'tvrage_id': 404},
            show_name='Wrong Name',
        )

        assert result['id'] == 101
        mock_request.assert_called_once_with('/lookup/shows', {'thetvdb': 202})

    def test_tvmaze_lookup_falls_back_through_external_ids_to_name(self, mocker):
        mock_request = mocker.patch.object(TVMazeService, '_request')
        mock_request.side_effect = [
            requests.RequestException('TVDB unavailable'),
            requests.RequestException('IMDb unavailable'),
            requests.RequestException('TV Rage unavailable'),
            [{'show': {'id': 505, 'name': 'Fallback Show', 'premiered': '2020-01-01'}}],
        ]

        result = TVMazeService().lookup_show(
            external_ids={'tvdb_id': 202, 'imdb_id': 'tt303', 'tvrage_id': 404},
            show_name='Fallback Show',
            year=2020,
        )

        assert result['id'] == 505
        assert mock_request.call_args_list[-1].args == ('/search/shows', {'q': 'Fallback Show'})

    def test_tvmaze_404_is_negatively_cached(self, mocker):
        service = TVMazeService()
        response = MagicMock(status_code=404)
        mock_get = mocker.patch.object(service._session, 'get', return_value=response)

        assert service.lookup_show_by_id(999) is None
        assert service.lookup_show_by_id(999) is None

        mock_get.assert_called_once()

    def test_tvmaze_timeout_stops_lookup_chain_and_opens_breaker(self, mocker):
        service = TVMazeService()
        mock_get = mocker.patch.object(service._session, 'get', side_effect=requests.Timeout('slow'))

        result = service.lookup_show(
            external_ids={'tvdb_id': 202, 'imdb_id': 'tt303', 'tvrage_id': 404},
            show_name='Fallback Show',
        )

        assert result is None
        mock_get.assert_called_once()
        assert service.lookup_show_by_id(100) is None
        mock_get.assert_called_once()

    def test_tvmaze_external_ids_are_persisted_with_tvmaze_id(self):
        with patch.object(tmdb, 'get_tv_details', return_value={
            'id': 888,
            'name': 'External ID Show',
            'first_air_date': '2020-01-01',
            'number_of_seasons': 0,
            'number_of_episodes': 0,
            'external_ids': {
                'tvdb_id': 123,
                'imdb_id': 'tt456',
                'tvrage_id': 789,
                'wikidata_id': 'Q123',
            },
            'genres': [],
            'networks': [],
        }), patch.object(tmdb, '_resolve_tvmaze', return_value=({'id': 321}, [])):
            show = tmdb.sync_tv_show(888, recompute_user_statuses=False)

        assert show.external_ids == {
            'tvdb_id': 123,
            'imdb_id': 'tt456',
            'tvrage_id': 789,
            'tvmaze_id': 321,
        }

    def test_episode_runtime_uses_tvmaze_when_tmdb_runtime_is_missing(self):
        show = TVShow.objects.create(tmdb_id=990, name='Runtime Fallback Show')
        season_data = {
            'id': 9901,
            'season_number': 1,
            'name': 'Season 1',
            'episodes': [{'id': 99011, 'episode_number': 1, 'name': 'Episode 1'}],
        }

        with patch.object(tvmaze, 'lookup_season_show', return_value=None):
            tmdb._upsert_season(
                show,
                1,
                season_data,
                tvmaze_show={'network': {'country': {'timezone': 'UTC'}}},
                tvmaze_episodes=[{'season': 1, 'number': 1, 'airdate': '2026-01-01', 'airtime': '20:00', 'runtime': 47}],
            )

        assert show.seasons.get(season_number=1).episodes.get(episode_number=1).runtime == 47

    def test_episode_effective_runtime_falls_back_to_show_runtime(self):
        show = TVShow.objects.create(tmdb_id=995, name='Effective Runtime Show', episode_runtime=45)
        season = Season.objects.create(show=show, tmdb_id=9951, season_number=1, name='Season 1')
        episode = Episode.objects.create(season=season, tmdb_id=99511, episode_number=1, name='No runtime')

        assert episode.effective_runtime == 45

        episode.runtime = 30
        assert episode.effective_runtime == 30

        episode.runtime = None
        show.episode_runtime = None
        assert episode.effective_runtime is None

    def test_episode_runtime_keeps_tmdb_value_over_tvmaze_runtime(self):
        show = TVShow.objects.create(tmdb_id=991, name='Runtime Precedence Show')
        season_data = {
            'id': 9911,
            'season_number': 1,
            'name': 'Season 1',
            'episodes': [{'id': 99111, 'episode_number': 1, 'name': 'Episode 1', 'runtime': 42}],
        }

        with patch.object(tvmaze, 'lookup_season_show', return_value=None):
            tmdb._upsert_season(
                show,
                1,
                season_data,
                tvmaze_show={'network': {'country': {'timezone': 'UTC'}}},
                tvmaze_episodes=[{'season': 1, 'number': 1, 'airdate': '2026-01-01', 'airtime': '20:00', 'runtime': 47}],
            )

        assert show.seasons.get(season_number=1).episodes.get(episode_number=1).runtime == 42

    def test_tv_show_runtime_uses_tvmaze_when_tmdb_runtime_is_missing(self):
        show_data = {
            'id': 994,
            'name': 'Show Runtime Fallback',
            'first_air_date': '2026-01-01',
            'number_of_seasons': 0,
            'number_of_episodes': 0,
            'episode_run_time': [],
            'genres': [],
            'networks': [],
        }
        with (
            patch.object(tmdb, 'get_tv_details', return_value=show_data),
            patch.object(tmdb, '_resolve_tvmaze', return_value=({'id': 9941, 'runtime': 52}, [])),
        ):
            show = tmdb.sync_tv_show(994, recompute_user_statuses=False)

        assert show.episode_runtime == 52

    def test_season_context_overrides_parent_tvmaze_mapping_for_split_show(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 48945},
        )
        split_show = {'id': 88337, 'name': 'Cyberpunk: Edgerunners 2'}
        split_episodes = [
            {'id': 3707058, 'season': 1, 'number': 1, 'name': 'Episode 1', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
            {'id': 3707059, 'season': 1, 'number': 2, 'name': 'Episode 2', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
        ]
        payloads = {
            1: {'episode_number': 1, 'name': 'Episode 1', 'air_date': '2026-10-20'},
            2: {'episode_number': 2, 'name': 'Episode 2', 'air_date': '2026-10-20'},
        }

        def get_episodes(tvmaze_id):
            return split_episodes if tvmaze_id == 88337 else []

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value={'id': 48945, 'name': 'Cyberpunk: Edgerunners'}),
            patch.object(tvmaze, 'lookup_season_show', return_value=split_show) as mock_season_lookup,
            patch.object(tvmaze, 'get_show_episodes', side_effect=get_episodes),
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None, payloads=payloads)

        assert resolved['id'] == 88337
        assert episodes == split_episodes
        assert season.external_ids['tvmaze_id'] == 88337
        mock_season_lookup.assert_called_once_with(
            external_ids=None,
            season_name='Cyberpunk: Edgerunners 2',
            year=None,
        )

    def test_split_season_matches_tvmaze_episodes_with_restarted_numbering(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        tvmaze_show = {'id': 88337, 'name': 'Cyberpunk: Edgerunners 2'}
        tvmaze_episodes = [
            {'id': 3707058 + index, 'season': 1, 'number': index + 1, 'name': 'TBA', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25}
            for index in range(2)
        ]

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value={'id': 48945, 'name': 'Cyberpunk: Edgerunners'}),
            patch.object(tvmaze, 'lookup_season_show', return_value=tvmaze_show),
            patch.object(tvmaze, 'get_show_episodes', return_value=tvmaze_episodes),
        ):
            tmdb._upsert_season(
                show,
                2,
                {
                    'id': 1052482,
                    'season_number': 2,
                    'name': 'Cyberpunk: Edgerunners 2',
                    'air_date': '2026-10-20',
                    'episodes': [
                        {'id': 10524821 + index, 'episode_number': index + 1, 'name': f'Episode {index + 1}', 'air_date': '2026-10-20'}
                        for index in range(2)
                    ],
                },
                tvmaze_context={},
            )

        season = show.seasons.get(season_number=2)
        assert season.external_ids['tvmaze_id'] == 88337
        assert list(season.episodes.order_by('episode_number').values_list('external_ids', flat=True)) == [
            {'tvmaze_id': 3707058, 'tvmaze_show_id': 88337},
            {'tvmaze_id': 3707059, 'tvmaze_show_id': 88337},
        ]
        assert list(season.episodes.order_by('episode_number').values_list('runtime', flat=True)) == [25, 25]

    def test_named_season_with_parent_episode_coverage_stays_on_parent(self):
        show = TVShow.objects.create(
            tmdb_id=111110,
            name='ONE PIECE',
            external_ids={'tvmaze_id': 46065},
        )
        tvmaze_show = {'id': 46065, 'name': 'ONE PIECE'}
        tvmaze_episodes = [
            {'id': 1, 'season': 1, 'number': 1, 'name': 'Romance Dawn', 'airdate': '2023-08-31'},
            {'id': 2, 'season': 2, 'number': 1, 'name': 'THE BEGINNING AND THE END', 'airdate': '2026-03-10'},
            {'id': 3, 'season': 2, 'number': 2, 'name': 'GOOD WHALE HUNTING', 'airdate': '2026-03-10'},
        ]

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value=tvmaze_show),
            patch.object(tvmaze, 'get_show_episodes', return_value=tvmaze_episodes),
            patch.object(tvmaze, 'lookup_season_show') as mock_season_search,
        ):
            tmdb._upsert_season(
                show,
                2,
                {
                    'id': 400466,
                    'season_number': 2,
                    'name': 'Into the Grand Line',
                    'air_date': '2026-03-10',
                    'episodes': [
                        {'id': 40046601, 'episode_number': 1, 'name': 'THE BEGINNING AND THE END', 'air_date': '2026-03-10'},
                        {'id': 40046602, 'episode_number': 2, 'name': 'GOOD WHALE HUNTING', 'air_date': '2026-03-10'},
                    ],
                },
                tvmaze_context={},
            )

        season = show.seasons.get(season_number=2)
        assert season.external_ids['tvmaze_id'] == 46065
        assert list(season.episodes.order_by('episode_number').values_list('external_ids', flat=True)) == [
            {'tvmaze_id': 2, 'tvmaze_show_id': 46065},
            {'tvmaze_id': 3, 'tvmaze_show_id': 46065},
        ]
        mock_season_search.assert_not_called()

    def test_named_season_rejects_unrelated_tvmaze_show(self):
        show = TVShow.objects.create(
            tmdb_id=111110,
            name='ONE PIECE',
            external_ids={'tvmaze_id': 46065},
        )
        parent_show = {'id': 46065, 'name': 'ONE PIECE'}
        parent_episodes = [
            {'id': 1, 'season': 2, 'number': 1, 'name': 'THE BEGINNING AND THE END', 'airdate': '2026-03-10'},
        ]
        unrelated_show = {'id': 99999, 'name': 'The Battle of Alabasta'}
        unrelated_episodes = [
            {'id': 999, 'season': 1, 'number': 1, 'name': 'Something Else', 'airdate': '2020-01-01'},
        ]

        def get_episodes(tvmaze_id):
            return unrelated_episodes if tvmaze_id == 99999 else parent_episodes

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value=parent_show),
            patch.object(tvmaze, 'get_show_episodes', side_effect=get_episodes),
            patch.object(tvmaze, 'lookup_season_show', return_value=unrelated_show),
        ):
            tmdb._upsert_season(
                show,
                3,
                {
                    'id': 503369,
                    'season_number': 3,
                    'name': 'The Battle of Alabasta',
                    'air_date': None,
                    'episodes': [
                        {'id': 50336901, 'episode_number': 1, 'name': "WHERE THERE'S SMOKE", 'air_date': None},
                    ],
                },
                tvmaze_context={},
            )

        season = show.seasons.get(season_number=3)
        episode = season.episodes.get(episode_number=1)
        assert season.external_ids['tvmaze_id'] == 46065
        assert episode.external_ids == {}

    def test_stored_nonparent_tvmaze_id_with_matching_payloads_is_trusted(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 88337},
        )
        stored_episodes = [
            {'id': 3707058, 'season': 1, 'number': 1, 'name': 'Episode 1', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
            {'id': 3707059, 'season': 1, 'number': 2, 'name': 'Episode 2', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
        ]
        payloads = {
            1: {'episode_number': 1, 'name': 'Episode 1', 'air_date': '2026-10-20'},
            2: {'episode_number': 2, 'name': 'Episode 2', 'air_date': '2026-10-20'},
        }

        def get_episodes(tvmaze_id):
            return stored_episodes if tvmaze_id == 88337 else []

        with (
            patch.object(tvmaze, 'lookup_show_by_id', side_effect=lambda value: {'id': value, 'name': 'Stored Show'}),
            patch.object(tvmaze, 'get_show_episodes', side_effect=get_episodes),
            patch.object(tvmaze, 'lookup_season_show') as mock_season_search,
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None, payloads=payloads)

        assert resolved['id'] == 88337
        assert episodes == stored_episodes
        assert season.external_ids['tvmaze_id'] == 88337
        mock_season_search.assert_not_called()

    def test_stored_nonparent_tvmaze_id_with_mismatched_payloads_searches(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 99999},
        )
        stored_episodes = [
            {'id': 999, 'season': 1, 'number': 1, 'name': 'Different Episode', 'airdate': '2020-01-01', 'airtime': '', 'runtime': 25},
        ]
        candidate_show = {'id': 88337, 'name': 'Cyberpunk: Edgerunners 2'}
        candidate_episodes = [
            {'id': 3707058, 'season': 1, 'number': 1, 'name': 'Episode 1', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
            {'id': 3707059, 'season': 1, 'number': 2, 'name': 'Episode 2', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
        ]
        payloads = {
            1: {'episode_number': 1, 'name': 'Episode 1', 'air_date': '2026-10-20'},
            2: {'episode_number': 2, 'name': 'Episode 2', 'air_date': '2026-10-20'},
        }

        def get_episodes(tvmaze_id):
            if tvmaze_id == 99999:
                return stored_episodes
            if tvmaze_id == 88337:
                return candidate_episodes
            return []

        with (
            patch.object(tvmaze, 'lookup_show_by_id', side_effect=lambda value: {'id': value, 'name': 'Stored Show'}),
            patch.object(tvmaze, 'get_show_episodes', side_effect=get_episodes),
            patch.object(tvmaze, 'lookup_season_show', return_value=candidate_show) as mock_season_search,
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None, payloads=payloads)

        assert resolved['id'] == 88337
        assert episodes == candidate_episodes
        assert season.external_ids['tvmaze_id'] == 88337
        mock_season_search.assert_called_once()

    def test_empty_payloads_do_not_trigger_name_search(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
        )

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value={'id': 48945, 'name': 'Cyberpunk: Edgerunners'}),
            patch.object(tvmaze, 'get_show_episodes', return_value=[]),
            patch.object(tvmaze, 'lookup_season_show') as mock_season_search,
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None, payloads={})

        assert resolved['id'] == 48945
        assert episodes == []
        mock_season_search.assert_not_called()

    def test_stored_nonparent_tvmaze_id_with_partial_overlap_is_rejected(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 99999},
        )
        stored_episodes = [
            {'id': 999, 'season': 1, 'number': 1, 'name': 'Episode 1', 'airdate': '2026-10-20', 'airtime': '', 'runtime': 25},
        ]
        payloads = {
            1: {'episode_number': 1, 'name': 'Episode 1', 'air_date': '2026-10-20'},
            2: {'episode_number': 2, 'name': 'Episode 2', 'air_date': '2026-10-20'},
        }

        def lookup_show(tvmaze_id):
            return {'id': tvmaze_id, 'name': 'Stored Show'} if tvmaze_id == 99999 else {'id': 48945, 'name': 'Parent Show'}

        def get_episodes(tvmaze_id):
            return stored_episodes if tvmaze_id == 99999 else []

        with (
            patch.object(tvmaze, 'lookup_show_by_id', side_effect=lookup_show),
            patch.object(tvmaze, 'get_show_episodes', side_effect=get_episodes),
            patch.object(tvmaze, 'lookup_season_show', return_value=None),
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None, payloads=payloads)

        assert resolved['id'] == 48945
        assert episodes == []

    def test_stored_nonparent_tvmaze_id_without_payloads_is_trusted(self):
        show = TVShow.objects.create(
            tmdb_id=105248,
            name='Cyberpunk: Edgerunners',
            external_ids={'tvmaze_id': 48945},
        )
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 99999},
        )

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value={'id': 99999, 'name': 'Stored Show'}),
            patch.object(tvmaze, 'get_show_episodes', return_value=[]),
            patch.object(tvmaze, 'lookup_season_show') as mock_season_search,
        ):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None)

        assert resolved['id'] == 99999
        assert episodes == []
        assert season.external_ids['tvmaze_id'] == 99999
        mock_season_search.assert_not_called()

    def test_parent_count_mismatch_with_matching_metadata_keeps_parent(self):
        show = TVShow.objects.create(
            tmdb_id=111110,
            name='ONE PIECE',
            external_ids={'tvmaze_id': 46065},
        )
        parent_show = {'id': 46065, 'name': 'ONE PIECE'}
        parent_episodes = [
            {'id': 1, 'season': 2, 'number': 1, 'name': 'THE BEGINNING AND THE END', 'airdate': '2026-03-10'},
            {'id': 2, 'season': 2, 'number': 2, 'name': 'GOOD WHALE HUNTING', 'airdate': '2026-03-10'},
            {'id': 3, 'season': 2, 'number': 3, 'name': 'WHISKY BUSINESS', 'airdate': '2026-03-10'},
        ]

        with (
            patch.object(tvmaze, 'lookup_show_by_id', return_value=parent_show),
            patch.object(tvmaze, 'get_show_episodes', return_value=parent_episodes),
            patch.object(tvmaze, 'lookup_season_show') as mock_season_search,
        ):
            tmdb._upsert_season(
                show,
                2,
                {
                    'id': 400466,
                    'season_number': 2,
                    'name': 'Into the Grand Line',
                    'air_date': '2026-03-10',
                    'episodes': [
                        {'id': 40046601, 'episode_number': 1, 'name': 'THE BEGINNING AND THE END', 'air_date': '2026-03-10'},
                        {'id': 40046602, 'episode_number': 2, 'name': 'GOOD WHALE HUNTING', 'air_date': '2026-03-10'},
                    ],
                },
                tvmaze_context={},
            )

        season = show.seasons.get(season_number=2)
        assert season.external_ids['tvmaze_id'] == 46065
        assert list(season.episodes.order_by('episode_number').values_list('external_ids', flat=True)) == [
            {'tvmaze_id': 1, 'tvmaze_show_id': 46065},
            {'tvmaze_id': 2, 'tvmaze_show_id': 46065},
        ]
        mock_season_search.assert_not_called()

    def test_season_sync_preserves_stored_tvmaze_mapping(self):
        show = TVShow.objects.create(tmdb_id=105248, name='Cyberpunk: Edgerunners')
        season = show.seasons.create(
            tmdb_id=1052482,
            season_number=2,
            name='Cyberpunk: Edgerunners 2',
            external_ids={'tvmaze_id': 88337},
        )

        tmdb._upsert_season_record(
            show,
            2,
            {'id': 1052482, 'name': 'Cyberpunk: Edgerunners 2', 'external_ids': {'tvdb_id': 2194943}},
        )

        season.refresh_from_db()
        assert season.external_ids == {'tvmaze_id': 88337, 'tvdb_id': 2194943}

    def test_season_specific_tvmaze_show_matches_different_provider_numbering(self):
        show = TVShow.objects.create(tmdb_id=30984, name='Bleach')
        with patch.object(tvmaze, 'lookup_season_show', return_value={'id': 80375, 'network': {'country': {'timezone': 'Asia/Tokyo'}}}), patch.object(
            tvmaze,
            'get_show_episodes',
            return_value=[{'id': 3691961, 'season': 4, 'number': 8, 'name': 'The End Two World', 'airdate': '2026-09-12', 'airtime': '23:00'}],
        ):
            tmdb._upsert_season(
                show,
                2,
                {
                    'id': 295738,
                    'season_number': 2,
                    'name': 'Thousand-Year Blood War',
                    'air_date': '2022-10-10',
                    'external_ids': {'imdb_id': 'tt14986406'},
                    'episodes': [{'id': 7470579, 'episode_number': 48, 'name': 'THE END TWO WORLD', 'air_date': '2026-09-12'}],
                },
                tvmaze_context={},
            )

        season = show.seasons.get(season_number=2)
        episode = season.episodes.get(episode_number=48)
        assert season.external_ids['tvmaze_id'] == 80375
        assert episode.external_ids['tvmaze_id'] == 3691961
        assert episode.external_ids['tvmaze_show_id'] == 80375
        assert episode.local_broadcast_datetime.strftime('%H:%M') == '16:00'

    def test_unmatched_episode_uses_tvmaze_show_schedule(self):
        show = TVShow.objects.create(tmdb_id=65942, name='Re:ZERO -Starting Life in Another World-')
        tmdb._upsert_season(
            show,
            1,
            {
                'id': 6594201,
                'season_number': 1,
                'name': 'Season 1',
                'air_date': '2016-04-04',
                'episodes': [{
                    'id': 659420101,
                    'episode_number': 82,
                    'name': 'Episode 82',
                    'air_date': '2026-09-09',
                }],
            },
            tvmaze_show={
                'id': 14459,
                'schedule': {'time': '22:30'},
                'network': {'country': {'timezone': 'Asia/Tokyo'}},
            },
            tvmaze_episodes=[],
        )

        episode = show.seasons.get(season_number=1).episodes.get(episode_number=82)
        assert episode.external_ids == {}
        assert episode.local_broadcast_datetime.isoformat() == '2026-09-09T15:30:00+02:00'

    def test_matched_episode_without_tvmaze_airtime_uses_show_schedule(self):
        show = TVShow.objects.create(tmdb_id=65942, name='Re:ZERO -Starting Life in Another World-')
        tmdb._upsert_season(
            show,
            1,
            {
                'id': 6594201,
                'season_number': 1,
                'name': 'Season 1',
                'air_date': '2016-04-04',
                'episodes': [{'id': 659420101, 'episode_number': 1, 'name': 'Episode 1', 'air_date': '2016-04-04'}],
            },
            tvmaze_show={
                'id': 14459,
                'schedule': {'time': '22:30'},
                'network': {'country': {'timezone': 'Asia/Tokyo'}},
            },
            tvmaze_episodes=[{'id': 1, 'season': 1, 'number': 1, 'name': 'Episode 1', 'airdate': '2016-04-04', 'airtime': ''}],
        )

        episode = show.seasons.get(season_number=1).episodes.get(episode_number=1)
        assert episode.local_broadcast_datetime.isoformat() == '2016-04-04T15:30:00+02:00'

    def test_season_context_falls_back_to_parent_tvmaze_show(self):
        show = TVShow.objects.create(
            tmdb_id=65942,
            name='Re:ZERO -Starting Life in Another World-',
            external_ids={'tvmaze_id': 14459},
        )
        season = show.seasons.create(tmdb_id=6594201, season_number=1, name='Season 1')
        with patch.object(tmdb, '_resolve_tvmaze_season', return_value=None), patch.object(
            tvmaze, 'lookup_show_by_id', return_value={'id': 14459}
        ) as lookup, patch.object(tvmaze, 'get_show_episodes', return_value=[]):
            resolved, episodes = tmdb._season_tvmaze_context(show, season, {}, None, None)

        assert resolved['id'] == 14459
        assert episodes == []
        lookup.assert_called_once_with(14459)

    def test_sync_overwrites_existing_episode_broadcast_start(self):
        show = TVShow.objects.create(tmdb_id=65942, name='Re:ZERO -Starting Life in Another World-')
        season = show.seasons.create(tmdb_id=6594201, season_number=1, name='Season 1')
        season.episodes.create(
            tmdb_id=659420101,
            episode_number=1,
            name='Episode 1',
            air_date='2016-04-04',
            broadcast_start=timezone.make_aware(timezone.datetime(2016, 4, 4, 0, 0)),
        )

        tmdb._upsert_season(
            show,
            1,
            {
                'id': 6594201,
                'season_number': 1,
                'name': 'Season 1',
                'episodes': [{'id': 659420101, 'episode_number': 1, 'name': 'Episode 1', 'air_date': '2016-04-04'}],
            },
            tvmaze_show={'id': 14459, 'schedule': {'time': '22:30'}, 'network': {'country': {'timezone': 'Asia/Tokyo'}}},
            tvmaze_episodes=[],
        )

        episode = season.episodes.get(episode_number=1)
        assert episode.local_broadcast_datetime.isoformat() == '2016-04-04T15:30:00+02:00'

    def test_movie_popular(self, auth_client):
        response = auth_client.get('/api/media/popular/?type=movie')
        assert response.status_code == 200

    def test_movie_detail(self, auth_client):
        response = auth_client.get('/api/media/movies/550/')  # Fight Club
        assert response.status_code in [200, 404]

    def test_tv_popular(self, auth_client):
        response = auth_client.get('/api/media/popular/?type=tv')
        assert response.status_code == 200

    def test_tv_detail(self, auth_client):
        response = auth_client.get('/api/media/tv/1399/')  # Game of Thrones
        assert response.status_code in [200, 404]

    def test_tv_detail_includes_episode_runtime(self, auth_client):
        response = auth_client.get('/api/media/tv/1399/')
        assert response.status_code == 200
        assert response.data['episode_runtime'] == 57

    def test_search(self, auth_client):
        response = auth_client.get('/api/media/search/?q=inception')
        assert response.status_code == 200

    def test_trending(self, auth_client):
        response = auth_client.get('/api/media/trending/')
        assert response.status_code == 200

    def test_genres_list_returns_sorted_genres(self, auth_client):
        Genre.objects.create(tmdb_id=1002, name='Thriller')
        Genre.objects.create(tmdb_id=1001, name='Action')

        response = auth_client.get('/api/media/genres/')
        assert response.status_code == 200
        assert [row['name'] for row in response.data] == ['Action', 'Thriller']

    def test_season_detail(self, auth_client):
        response = auth_client.get('/api/media/tv/1399/seasons/1/')
        assert response.status_code == 200

    def test_season_detail_includes_episode_type(self, auth_client):
        response = auth_client.get('/api/media/tv/1399/seasons/1/')
        assert response.status_code == 200
        assert response.data['episodes'][0]['episode_type'] == 'finale'

    def test_season_detail_uses_show_runtime_when_episode_runtime_is_missing(self, auth_client):
        show = TVShow.objects.create(tmdb_id=996, name='Show Runtime Fallback', episode_runtime=47)
        season = Season.objects.create(show=show, tmdb_id=9961, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=99611, episode_number=1, name='No runtime')
        Episode.objects.create(season=season, tmdb_id=99612, episode_number=2, name='Has runtime', runtime=30)

        response = auth_client.get(f'/api/media/tv/{show.tmdb_id}/seasons/1/')

        assert response.status_code == 200
        assert [episode['runtime'] for episode in response.data['episodes']] == [47, 30]

    def test_episode_detail(self, auth_client):
        response = auth_client.get('/api/media/tv/1399/seasons/1/episodes/1/credits/')
        assert response.status_code == 200

    def test_sync_tv_show_persists_episode_type(self):
        tmdb.sync_tv_show(1399)
        show = TVShow.objects.get(tmdb_id=1399)
        season = show.seasons.get(season_number=1)
        episode = season.episodes.get(episode_number=1)
        assert episode.episode_type == 'finale'

    def test_non_empty_defaults_drops_only_null_and_empty_containers(self):
        filtered = _non_empty_defaults(
            {
                'overview': '',
                'poster_path': None,
                'cast': [],
                'vote_average': 0,
                'title': 'Kept',
                'crew': ['kept'],
            }
        )
        assert filtered == {'vote_average': 0, 'title': 'Kept', 'crew': ['kept']}

    def test_sync_movie_preserves_stored_fields_when_tmdb_returns_empty(self):
        Movie.objects.create(
            tmdb_id=550,
            title='Fight Club',
            overview='Stored overview',
            poster_path='/stored.jpg',
            tagline='Stored tagline',
            vote_average=7.5,
        )

        def sparse_payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Fight Club',
                    'overview': '',
                    'poster_path': None,
                    'backdrop_path': None,
                    'release_date': '1999-10-15',
                    'genres': [],
                    'vote_average': 8.1,
                    'vote_count': 100,
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=sparse_payload):
            movie = tmdb.sync_movie(550)

        movie.refresh_from_db()
        assert movie.overview == 'Stored overview'
        assert movie.poster_path == '/stored.jpg'
        assert movie.tagline == 'Stored tagline'
        assert movie.vote_average == 8.1

    def test_sync_movie_detects_aftercredits_stinger(self):
        def payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Fight Club',
                    'overview': 'Mocked movie',
                    'release_date': '1999-10-15',
                    'genres': [],
                    'keywords': {
                        'keywords': [
                            {'id': 179430, 'name': 'after credits stinger'},
                        ],
                    },
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=payload):
            movie = tmdb.sync_movie(550)

        assert movie.has_postcredits_scene

    def test_sync_movie_detects_duringcredits_stinger(self):
        def payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Fight Club',
                    'overview': 'Mocked movie',
                    'release_date': '1999-10-15',
                    'genres': [],
                    'keywords': {
                        'keywords': [
                            {'id': 179431, 'name': 'during credits stinger'},
                        ],
                    },
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=payload):
            movie = tmdb.sync_movie(550)

        assert movie.has_postcredits_scene

    def test_sync_movie_no_postcredits_scene(self):
        def payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Fight Club',
                    'overview': 'Mocked movie',
                    'release_date': '1999-10-15',
                    'genres': [],
                    'keywords': {
                        'keywords': [
                            {'id': 999999, 'name': 'some other keyword'},
                        ],
                    },
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=payload):
            movie = tmdb.sync_movie(550)

        assert not movie.has_postcredits_scene

    def test_sync_movie_preserves_postcredits_when_keywords_missing(self):
        Movie.objects.create(
            tmdb_id=550,
            title='Fight Club',
            has_postcredits_scene=True,
        )

        def sparse_payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Fight Club',
                    'overview': '',
                    'poster_path': None,
                    'backdrop_path': None,
                    'release_date': '1999-10-15',
                    'genres': [],
                    'vote_average': 8.1,
                    'vote_count': 100,
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=sparse_payload):
            movie = tmdb.sync_movie(550)

        movie.refresh_from_db()
        assert movie.has_postcredits_scene

    def test_movie_detail_includes_postcredits_scene(self, auth_client):
        Movie.objects.create(
            tmdb_id=550,
            title='Fight Club',
            has_postcredits_scene=True,
        )

        response = auth_client.get('/api/media/movies/550/')
        assert response.status_code == 200
        assert response.data['has_postcredits_scene']

    def test_sync_movie_creation_stores_sparse_payload(self):
        def sparse_payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/601':
                return {
                    'id': 601,
                    'title': 'Sparse Movie',
                    'overview': '',
                    'poster_path': None,
                    'genres': [],
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=sparse_payload):
            movie = tmdb.sync_movie(601)

        assert Movie.objects.filter(tmdb_id=601).count() == 1
        movie.refresh_from_db()
        assert movie.title == 'Sparse Movie'
        assert movie.overview == ''
        assert movie.poster_path == ''

    def test_sync_tv_show_preserves_stored_fields_when_tmdb_removes_data(self):
        TVShow.objects.create(
            tmdb_id=1399,
            name='Game of Thrones',
            overview='Stored overview',
            status='Returning Series',
            networks='HBO',
        )

        def sparse_payload(endpoint, params=None, **kwargs):
            if endpoint == '/tv/1399':
                return {
                    'id': 1399,
                    'name': 'Game of Thrones',
                    'overview': '',
                    'networks': [],
                    'number_of_seasons': 0,
                    'genres': [],
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=sparse_payload):
            show = tmdb.sync_tv_show(1399)

        show.refresh_from_db()
        assert show.overview == 'Stored overview'
        assert show.status == 'Returning Series'
        assert show.networks == 'HBO'

    def test_sync_season_preserves_episode_fields_when_tmdb_returns_empty(self):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones')
        season = Season.objects.create(
            show=show,
            tmdb_id=139901,
            season_number=1,
            name='Season 1',
            overview='Stored season overview',
            poster_path='/stored-season.jpg',
        )
        Episode.objects.create(
            season=season,
            tmdb_id=13990101,
            episode_number=1,
            name='Winter Is Coming',
            overview='Stored episode overview',
            still_path='/still.jpg',
        )

        def sparse_payload(endpoint, params=None, **kwargs):
            if endpoint == '/tv/1399/season/1':
                return {
                    'id': 139901,
                    'season_number': 1,
                    'name': 'Season 1',
                    'overview': '',
                    'poster_path': None,
                    'episode_count': 10,
                    'episodes': [
                        {
                            'id': 13990101,
                            'episode_number': 1,
                            'name': 'Winter Is Coming',
                            'overview': '',
                            'still_path': None,
                            'runtime': None,
                        }
                    ],
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=sparse_payload):
            tmdb.sync_season(show, 1)

        season = show.seasons.get(season_number=1)
        episode = season.episodes.get(episode_number=1)
        assert season.overview == 'Stored season overview'
        assert season.poster_path == '/stored-season.jpg'
        assert episode.overview == 'Stored episode overview'
        assert episode.still_path == '/still.jpg'

    def test_sync_episode_credits_preserves_existing_lists_when_tmdb_returns_empty(self):
        tmdb.sync_tv_show(1399, sync_credits=True)
        show = TVShow.objects.get(tmdb_id=1399)
        episode = show.seasons.get(season_number=1).episodes.get(episode_number=1)
        credit = episode.credits
        credit.cast = [{'name': 'Emilia Clarke'}]
        credit.save(update_fields=['cast'])

        tmdb.sync_episode_credits(1399, 1, 1, show=show)

        credit.refresh_from_db()
        assert credit.cast == [{'name': 'Emilia Clarke'}]

    def test_sync_season_fetches_season_and_external_ids_in_one_request(self):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones')
        requested = []

        def capture(endpoint, params=None, **kwargs):
            requested.append((endpoint, (params or {}).get('append_to_response')))
            if endpoint == '/tv/1399/season/1':
                return {'id': 139901, 'season_number': 1, 'name': 'Season 1', 'external_ids': {'tvdb_id': 5}, 'episodes': []}
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=capture):
            season = tmdb.sync_season(show, 1)

        assert requested == [('/tv/1399/season/1', 'external_ids')]
        assert season.external_ids == {'tvdb_id': 5}

    def test_tv_detail_uses_user_preferred_region_when_region_missing(self, mocker, user, auth_client):
        mock_providers = mocker.patch('media.views.tmdb.get_tv_details')
        mocker.patch('media.views.tmdb.sync_season')
        user.preferred_region = 'ES'
        user.save(update_fields=['preferred_region'])

        TVShow.objects.create(
            tmdb_id=99999,
            name='Demo Show',
            number_of_seasons=0,
            number_of_episodes=0,
        )

        mock_providers.return_value = {'watch/providers': {
            'results': {
                'ES': {
                    'link': 'https://example.com/es',
                    'flatrate': [{'provider_id': 1, 'provider_name': 'Demo ES'}],
                }
            }
        }}

        response = auth_client.get('/api/media/tv/99999/')
        assert response.status_code == 200
        assert response.data['watch_providers']['region'] == 'ES'

    def test_popular_movies_includes_user_status_for_authenticated_user(self, mocker, user, auth_client):
        mock_popular = mocker.patch('media.views.tmdb.get_popular_movies')
        mock_popular.return_value = {
            'results': [
                {'id': 101, 'title': 'Movie A'},
                {'id': 102, 'title': 'Movie B'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 2,
        }
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=101, status='plan_to_watch')
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=102, watched_at='2026-08-01T10:00:00Z')
        Rating.objects.create(user=user, media_type='movie', tmdb_id=102, score=9)

        response = auth_client.get('/api/media/popular/?type=movie')
        assert response.status_code == 200
        first, second = response.data['results']
        assert first['user_status']['status'] == 'plan_to_watch'
        assert second['user_status']['status'] == 'watched'
        assert second['user_status']['rating'] == 9

    def test_search_multi_annotates_only_movie_and_tv(self, mocker, user, auth_client):
        mock_search_multi = mocker.patch('media.views.tmdb.search_multi')
        mock_search_multi.return_value = {
            'results': [
                {'id': 201, 'media_type': 'movie', 'title': 'Movie'},
                {'id': 202, 'media_type': 'tv', 'name': 'Show'},
                {'id': 203, 'media_type': 'person', 'name': 'Actor'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 3,
        }
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=201, status='plan_to_watch')
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=202, status='plan_to_watch')

        response = auth_client.get('/api/media/search/?q=test&type=multi')
        assert response.status_code == 200
        results = response.data['results']
        movie_entry = next(item for item in results if item['id'] == 201)
        tv_entry = next(item for item in results if item['id'] == 202)
        person_entry = next(item for item in results if item['id'] == 203)
        assert movie_entry['user_status']['status'] == 'plan_to_watch'
        assert tv_entry['user_status']['status'] == 'plan_to_watch'
        assert 'user_status' not in person_entry

    def test_search_multi_normalizes_tv_first_air_date_to_release_date(self, mocker, auth_client):
        mock_search_multi = mocker.patch('media.views.tmdb.search_multi')
        mock_search_multi.return_value = {
            'results': [
                {'id': 202, 'media_type': 'tv', 'name': 'Show', 'first_air_date': '2020-01-15'},
            ],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        response = auth_client.get('/api/media/search/?q=test&type=multi')
        assert response.status_code == 200
        result = response.data['results'][0]
        assert result['first_air_date'] == '2020-01-15'
        assert result['release_date'] == '2020-01-15'

    def test_search_prefixed_id_merges_dedupes_and_annotates(self, mocker, user, auth_client):
        mock_get_movie = mocker.patch('media.views.tmdb.get_movie')
        mock_get_tv = mocker.patch('media.views.tmdb.get_tv_show')
        mock_find_by_external_id = mocker.patch('media.views.tmdb.find_by_external_id')
        mock_get_movie.return_value = {
            'id': 550,
            'title': 'Fight Club',
            'release_date': '1999-10-15',
            'poster_path': '/movie.jpg',
        }
        mock_get_tv.return_value = {
            'id': 550,
            'name': 'Show 550',
            'first_air_date': '2019-01-01',
            'poster_path': '/show.jpg',
        }

        def fake_find(external_id, external_source):
            if external_source == 'imdb_id':
                return {
                    'movie_results': [
                        {'id': 550, 'title': 'Fight Club', 'media_type': 'movie'},
                        {'id': 777, 'title': 'Seven Seven Seven', 'media_type': 'movie'},
                    ],
                    'tv_results': [
                        {'id': 550, 'name': 'Show 550', 'media_type': 'tv'},
                    ],
                }
            return {'movie_results': [], 'tv_results': []}

        mock_find_by_external_id.side_effect = fake_find
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=550, status='plan_to_watch')
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=550, status='plan_to_watch')

        response = auth_client.get('/api/media/search/?q=%23550&type=multi')
        assert response.status_code == 200
        assert response.data['total_results'] == 3

        results = response.data['results']
        keys = {(row['media_type'], row['id']) for row in results}
        assert keys == {('movie', 550), ('tv', 550), ('movie', 777)}

        movie_550 = next(row for row in results if row['media_type'] == 'movie' and row['id'] == 550)
        tv_550 = next(row for row in results if row['media_type'] == 'tv' and row['id'] == 550)
        assert movie_550['user_status']['status'] == 'plan_to_watch'
        assert tv_550['user_status']['status'] == 'plan_to_watch'

    def test_search_prefixed_id_rejects_path_characters(self, mocker, auth_client):
        mock_find = mocker.patch('media.views.tmdb.find_by_external_id')
        mock_get_movie = mocker.patch('media.views.tmdb.get_movie')
        mock_get_tv = mocker.patch('media.views.tmdb.get_tv_show')
        for raw in ('../movie/550', 'tt1?x=1', 'tt1#frag', '..', 'a' * 65):
            response = auth_client.get('/api/media/search/', {'q': f'#{raw}'})
            assert response.status_code == 200
            assert response.data['results'] == []
        mock_find.assert_not_called()
        mock_get_movie.assert_not_called()
        mock_get_tv.assert_not_called()

    def test_trending_rejects_unknown_type_and_window(self, mocker, auth_client):
        mock_get_trending = mocker.patch('media.views.tmdb.get_trending')
        assert auth_client.get('/api/media/trending/', {'type': '../movie/550'}).status_code == 400
        assert auth_client.get('/api/media/trending/', {'window': 'month'}).status_code == 400
        mock_get_trending.assert_not_called()

    def test_search_prefixed_id_applies_scope_filter(self, mocker, auth_client):
        mock_find_by_external_id = mocker.patch('media.views.tmdb.find_by_external_id')
        mock_find_by_external_id.return_value = {
            'movie_results': [
                {'id': 10, 'title': 'Ten', 'media_type': 'movie'},
            ],
            'tv_results': [
                {'id': 20, 'name': 'Twenty', 'media_type': 'tv'},
            ],
        }

        movies_response = auth_client.get('/api/media/search/?q=%23tt0111161&type=movie')
        assert movies_response.status_code == 200
        assert len(movies_response.data['results']) == 1
        assert movies_response.data['results'][0]['media_type'] == 'movie'

        tv_response = auth_client.get('/api/media/search/?q=%23tt0111161&type=tv')
        assert tv_response.status_code == 200
        assert len(tv_response.data['results']) == 1
        assert tv_response.data['results'][0]['media_type'] == 'tv'

    def test_popular_tv_status_rules_exclude_season_zero_for_show_progress(self, mocker, user, auth_client):
        mock_popular = mocker.patch('media.views.tmdb.get_popular_tv')
        mock_popular.return_value = {
            'results': [{'id': 303, 'name': 'Show A'}],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        show = TVShow.objects.create(
            tmdb_id=303,
            name='Show A',
            number_of_seasons=2,
            number_of_episodes=3,
            status='Ended',
        )
        season_zero = show.seasons.create(tmdb_id=3000, season_number=0, name='Specials')
        season_one = show.seasons.create(tmdb_id=3001, season_number=1, name='Season 1')
        season_two = show.seasons.create(tmdb_id=3002, season_number=2, name='Season 2')
        season_zero.episodes.create(tmdb_id=1, episode_number=1, name='Special 1')
        season_one.episodes.create(tmdb_id=2, episode_number=1, name='Ep 1')
        season_one.episodes.create(tmdb_id=3, episode_number=2, name='Ep 2')
        season_two.episodes.create(tmdb_id=4, episode_number=1, name='Ep 1')

        # Only specials watched -> show status should remain unknown
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=303,
            season_number=0,
            episode_number=1,
            watched_at='2026-08-01T10:00:00Z',
        )

        response = auth_client.get('/api/media/popular/?type=tv')
        assert response.status_code == 200
        status_payload = response.data['results'][0]['user_status']
        assert status_payload['status'] is None
        assert status_payload['progress']['total_episodes'] == 0
        assert status_payload['progress']['watched_episodes'] == 0

        # Watch one non-special -> watching
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=303,
            season_number=1,
            episode_number=1,
            watched_at='2026-08-02T10:00:00Z',
        )
        response = auth_client.get('/api/media/popular/?type=tv')
        assert response.data['results'][0]['user_status']['status'] == 'watching'

        # Undated episodes are not released, so the show remains watching.
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=303,
            season_number=1,
            episode_number=2,
            watched_at='2026-08-03T10:00:00Z',
        )
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=303,
            season_number=2,
            episode_number=1,
            watched_at='2026-08-04T10:00:00Z',
        )
        response = auth_client.get('/api/media/popular/?type=tv')
        assert response.data['results'][0]['user_status']['status'] == 'watching'

    def test_season_detail_includes_season_zero_own_progress(self, user, auth_client):
        show = TVShow.objects.create(tmdb_id=404, name='Show B', number_of_seasons=1, number_of_episodes=2)
        season_zero = show.seasons.create(tmdb_id=4040, season_number=0, name='Specials')
        season_zero.episodes.create(tmdb_id=10, episode_number=1, name='S0E1')
        season_zero.episodes.create(tmdb_id=11, episode_number=2, name='S0E2')

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=404,
            season_number=0,
            episode_number=1,
            watched_at='2026-08-01T10:00:00Z',
        )

        response = auth_client.get('/api/media/tv/404/seasons/0/')
        assert response.status_code == 200
        assert response.data['user_status']['status'] == 'watching'
        assert response.data['user_status']['progress']['watched_episodes'] == 1
        assert response.data['user_status']['progress']['total_episodes'] == 2

    def test_season_detail_uses_db_first_when_season_exists(self, mocker, auth_client):
        mock_sync_season = mocker.patch('media.views.tmdb.sync_season')
        show = TVShow.objects.create(tmdb_id=505, name='Show DB First', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=5050, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=50501, episode_number=1, name='Existing Episode')

        response = auth_client.get('/api/media/tv/505/seasons/1/')

        assert response.status_code == 200
        assert response.data['season_number'] == 1
        assert response.data['episodes'][0]['name'] == 'Existing Episode'
        mock_sync_season.assert_not_called()

    def test_episode_credits_uses_db_first_when_present(self, mocker, auth_client):
        mock_sync_episode_credits = mocker.patch('media.views.tmdb.sync_episode_credits')
        show = TVShow.objects.create(tmdb_id=606, name='Show Credits', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=6060, season_number=1, name='Season 1')
        episode = season.episodes.create(tmdb_id=60601, episode_number=1, name='Episode 1')
        EpisodeCredit.objects.create(
            episode=episode,
            cast=[{'name': 'DB Cast Member'}],
            crew=[{'name': 'DB Crew Member', 'job': 'Director'}],
            guest_stars=[{'name': 'DB Guest'}],
        )

        response = auth_client.get('/api/media/tv/606/seasons/1/episodes/1/credits/')

        assert response.status_code == 200
        assert response.data['cast'][0]['name'] == 'DB Cast Member'
        assert response.data['crew'][0]['name'] == 'DB Crew Member'
        assert response.data['guest_stars'][0]['name'] == 'DB Guest'
        mock_sync_episode_credits.assert_not_called()

    def test_tv_heatmap_returns_seasons_with_episode_ratings(self, auth_client):
        show = TVShow.objects.create(tmdb_id=777, name='Heatmap Show', number_of_seasons=2, number_of_episodes=4)
        season1 = show.seasons.create(tmdb_id=7771, season_number=1, name='Season 1')
        season2 = show.seasons.create(tmdb_id=7772, season_number=2, name='Season 2')
        season1.episodes.create(tmdb_id=77711, episode_number=1, name='Ep 1', vote_average=8.5)
        season1.episodes.create(tmdb_id=77712, episode_number=2, name='Ep 2', vote_average=7.2)
        season2.episodes.create(tmdb_id=77721, episode_number=1, name='Ep 1', vote_average=9.0)
        season2.episodes.create(tmdb_id=77722, episode_number=2, name='Ep 2', vote_average=0)

        response = auth_client.get('/api/media/tv/777/heatmap/')
        assert response.status_code == 200
        assert len(response.data) == 2

        s1 = response.data[0]
        assert s1['season'] == 1
        assert len(s1['episodes']) == 2
        assert s1['episodes'][0]['episode'] == 1
        assert s1['episodes'][0]['rating'] == 8.5
        assert s1['episodes'][1]['episode'] == 2
        assert s1['episodes'][1]['rating'] == 7.2

        s2 = response.data[1]
        assert s2['season'] == 2
        assert s2['episodes'][1]['rating'] == 0

    def test_tv_heatmap_excludes_specials(self, auth_client):
        show = TVShow.objects.create(tmdb_id=778, name='Specials Show', number_of_seasons=1, number_of_episodes=1)
        season0 = show.seasons.create(tmdb_id=7780, season_number=0, name='Specials')
        season0.episodes.create(tmdb_id=77801, episode_number=1, name='Special 1', vote_average=5.0)
        season1 = show.seasons.create(tmdb_id=7781, season_number=1, name='Season 1')
        season1.episodes.create(tmdb_id=77811, episode_number=1, name='Ep 1', vote_average=8.0)

        response = auth_client.get('/api/media/tv/778/heatmap/')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['season'] == 1

    def test_tv_heatmap_requires_auth(self):
        anon = APIClient()
        response = anon.get('/api/media/tv/777/heatmap/')
        assert response.status_code == 401

    def test_episode_credits_fallback_syncs_and_persists(self, auth_client):
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=139901, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=13990101, episode_number=1, name='Winter Is Coming')

        response = auth_client.get('/api/media/tv/1399/seasons/1/episodes/1/credits/')

        assert response.status_code == 200
        assert 'cast' in response.data
        assert 'crew' in response.data
        assert 'guest_stars' in response.data
        assert EpisodeCredit.objects.filter(
                episode__season__show__tmdb_id=1399,
                episode__season__season_number=1,
                episode__episode_number=1,
            ).exists()

    def test_media_endpoints_require_authentication(self, mocker):
        mock_popular = mocker.patch('media.views.tmdb.get_popular_movies')
        anon = APIClient()
        mock_popular.return_value = {
            'results': [{'id': 555, 'title': 'Anon Movie'}],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        assert anon.get('/api/media/search/?q=test').status_code == 401
        assert anon.get('/api/media/trending/').status_code == 401
        assert anon.get('/api/media/popular/?type=movie').status_code == 401
        assert anon.get('/api/media/movies/550/').status_code == 401
        assert anon.get('/api/media/movies/550/credits/').status_code == 401
        assert anon.get('/api/media/tv/1399/').status_code == 401
        assert anon.get('/api/media/tv/1399/credits/').status_code == 401
        assert anon.get('/api/media/tv/1399/seasons/1/').status_code == 401
        assert anon.get('/api/media/tv/1399/seasons/1/episodes/1/credits/').status_code == 401
        assert anon.get('/api/media/tv/1399/external-ids/').status_code == 401
        assert anon.get('/api/media/tv/1399/recommendations/').status_code == 401
        assert anon.get('/api/media/movies/550/external-ids/').status_code == 401
        assert anon.get('/api/media/movies/550/recommendations/').status_code == 401
        assert anon.get('/api/media/collections/10/').status_code == 401
        assert anon.get('/api/media/tv/1399/seasons/1/credits/').status_code == 401

    def test_movie_detail_includes_user_status(self, mocker, user, auth_client):
        mock_providers = mocker.patch('media.views.tmdb.get_movie_details')
        mocker.patch('media.views.tmdb.sync_movie')
        from media.models import Movie
        Movie.objects.create(tmdb_id=777, title='Movie Detail')
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=777, status='plan_to_watch')
        Rating.objects.create(user=user, media_type='movie', tmdb_id=777, score=7)
        mock_providers.return_value = {}

        response = auth_client.get('/api/media/movies/777/')
        assert response.status_code == 200
        assert response.data['user_status']['status'] == 'plan_to_watch'
        # Ratings stay hidden until the movie leaves the watchlist.
        assert response.data['user_status']['rating'] is None

    def test_tv_detail_status_watching_and_dropped(self, mocker, user, auth_client):
        mock_providers = mocker.patch('media.views.tmdb.get_tv_details')
        mocker.patch('media.views.tmdb.sync_tv_show')
        show = TVShow.objects.create(tmdb_id=888, name='Show Detail', number_of_seasons=1, number_of_episodes=2)
        season = show.seasons.create(tmdb_id=8881, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=88811, episode_number=1, name='Ep 1')
        season.episodes.create(tmdb_id=88812, episode_number=2, name='Ep 2')
        mock_providers.return_value = {}

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=888,
            season_number=1,
            episode_number=1,
            watched_at='2026-08-01T10:00:00Z',
        )
        response = auth_client.get('/api/media/tv/888/')
        assert response.status_code == 200
        assert response.data['user_status']['status'] == 'watching'

        auth_client.post('/api/tracking/media/drop/', {'tmdb_id': 888, 'media_type': 'tv'})
        response = auth_client.get('/api/media/tv/888/')
        assert response.data['user_status']['status'] == 'dropped'
        assert 'status_changed_at' in response.data['user_status']

    def test_refresh_movie_metadata_requires_auth(self, mocker):
        mock_sync_movie = mocker.patch('media.views.tmdb.sync_movie')
        anon = APIClient()
        response = anon.post('/api/media/movies/550/refresh/', {}, format='json')
        assert response.status_code == 401
        mock_sync_movie.assert_not_called()

    def test_refresh_tv_metadata_requires_auth(self, mocker):
        mock_sync_tv_show = mocker.patch('media.views.tmdb.sync_tv_show')
        anon = APIClient()
        response = anon.post('/api/media/tv/1399/refresh/', {}, format='json')
        assert response.status_code == 401
        mock_sync_tv_show.assert_not_called()

    def test_refresh_movie_metadata_updates_and_returns_timestamp(self, mocker, auth_client):
        mock_sync_movie = mocker.patch('media.views.tmdb.sync_movie')
        movie = Movie.objects.create(tmdb_id=550, title='Fight Club')
        movie.title = 'Fight Club Updated'
        mock_sync_movie.return_value = movie

        response = auth_client.post('/api/media/movies/550/refresh/', {}, format='json')
        assert response.status_code == 200
        assert response.data['tmdb_id'] == 550
        assert 'metadata_updated_at' in response.data
        mock_sync_movie.assert_called_once_with(550, use_cache=False)

    def test_refresh_metadata_is_rate_limited(self, mocker, auth_client):
        mock_sync_movie = mocker.patch('media.views.tmdb.sync_movie')
        from django.conf import settings
        from django.core.cache import cache as django_cache

        mock_sync_movie.return_value = Movie.objects.create(tmdb_id=550, title='Fight Club')
        django_cache.clear()
        rates = {**settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'metadata_refresh': '1/hour'}
        with patch('rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES', rates):
            assert auth_client.post('/api/media/movies/550/refresh/').status_code == 200
            assert auth_client.post('/api/media/movies/550/refresh/').status_code == 429
            assert auth_client.post('/api/media/tv/1399/refresh/').status_code == 429
        assert mock_sync_movie.call_count == 1

    def test_refresh_tv_metadata_updates_show_and_seasons(self, mocker, user, auth_client):
        mock_sync_tv_show = mocker.patch('media.views.tmdb.sync_tv_show')
        mock_sync_credits_task = mocker.patch('media.views.sync_show_episode_credits')
        show = TVShow.objects.create(tmdb_id=1399, name='Game of Thrones', number_of_seasons=2, number_of_episodes=10)
        show.seasons.create(tmdb_id=139900, season_number=0, name='Specials')
        mock_sync_tv_show.return_value = show

        with TestCase.captureOnCommitCallbacks(execute=True):
            response = auth_client.post('/api/media/tv/1399/refresh/', {}, format='json')
        assert response.status_code == 200
        assert response.data['tmdb_id'] == 1399
        assert 'metadata_updated_at' in response.data
        mock_sync_tv_show.assert_called_once_with(
            1399,
            user_id=user.id,
            use_cache=False,
            only_seasons=None,
        )
        mock_sync_credits_task.delay.assert_called_once_with(1399, None, False)

    def test_tv_detail_cold_load_defers_episode_credits(self, mocker, auth_client):
        mock_credits_task = mocker.patch('media.views.sync_show_episode_credits')
        with patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])), TestCase.captureOnCommitCallbacks(execute=True):
            response = auth_client.get('/api/media/tv/1399/')

        assert response.status_code == 200
        assert Episode.objects.filter(
                season__show__tmdb_id=1399,
                season__season_number=1,
                episode_number=1,
            ).exists()
        assert not EpisodeCredit.objects.filter(episode__season__show__tmdb_id=1399).exists()
        mock_credits_task.delay.assert_called_once_with(1399, None, True)

    def test_tv_detail_resyncs_only_missing_seasons(self, mocker, user, auth_client):
        mock_providers = mocker.patch('media.views.tmdb.get_tv_details')
        mock_sync = mocker.patch('media.views.tmdb.sync_tv_show')
        mock_credits_task = mocker.patch('media.views.sync_show_episode_credits')
        mock_providers.return_value = {}
        show = TVShow.objects.create(tmdb_id=701, name='Partial Show', number_of_seasons=2, number_of_episodes=2)
        season_one = show.seasons.create(tmdb_id=7011, season_number=1, name='Season 1')
        season_one.episodes.create(tmdb_id=70111, episode_number=1, name='Episode 1')
        mock_sync.return_value = show

        with TestCase.captureOnCommitCallbacks(execute=True):
            response = auth_client.get('/api/media/tv/701/')

        assert response.status_code == 200
        mock_sync.assert_called_once_with(
            701, user_id=user.id, use_cache=True, only_seasons=[2]
        )
        mock_credits_task.delay.assert_called_once_with(701, [2], True)

    def test_tv_detail_skips_sync_when_complete(self, mocker, auth_client):
        mock_providers = mocker.patch('media.views.tmdb.get_tv_details')
        mock_sync = mocker.patch('media.views.tmdb.sync_tv_show')
        mock_credits_task = mocker.patch('media.views.sync_show_episode_credits')
        mock_providers.return_value = {}
        show = TVShow.objects.create(tmdb_id=702, name='Complete Show', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=7021, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=70211, episode_number=1, name='Episode 1')

        response = auth_client.get('/api/media/tv/702/')

        assert response.status_code == 200
        mock_sync.assert_not_called()
        mock_credits_task.delay.assert_not_called()

    def test_sync_tv_show_rebuilds_chain_once_for_many_episodes(self, mocker):
        mock_rebuild = mocker.patch('tracking.status_sync.rebuild_episode_chain')
        mock_refresh = mocker.patch('tracking.status_sync.refresh_all_statuses_for_show')
        season_payload = {
            'id': 139901,
            'season_number': 1,
            'name': 'Season 1',
            'episodes': [
                {'id': 13990101 + index, 'episode_number': index + 1, 'name': f'Episode {index + 1}'}
                for index in range(3)
            ],
        }
        with patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])), \
                patch.object(tmdb, 'get_season', return_value=season_payload):
            tmdb.sync_tv_show(1399)

        assert Episode.objects.filter(season__show__tmdb_id=1399).count() == 3
        mock_rebuild.assert_called_once_with(1399)
        mock_refresh.assert_called_once_with(1399, current_user_id=None)

    def test_season_tvmaze_context_reuses_episodes_for_same_show(self):
        show = TVShow.objects.create(tmdb_id=704, name='Reuse Show', external_ids={'tvmaze_id': 9001})
        season_one = show.seasons.create(tmdb_id=7041, season_number=1, name='Season 1')
        season_two = show.seasons.create(tmdb_id=7042, season_number=2, name='Season 2')
        episodes = [{'id': 1, 'season': 1, 'number': 1}]

        with patch.object(tvmaze, 'lookup_show_by_id', return_value={'id': 9001}), \
                patch.object(tvmaze, 'get_show_episodes', return_value=episodes) as mock_episodes:
            context: dict = {}
            tmdb._season_tvmaze_context(show, season_one, context, None, None)
            tmdb._season_tvmaze_context(show, season_two, context, None, None)

        mock_episodes.assert_called_once_with(9001)

    def test_season_brief_serialization_avoids_per_season_queries(self, django_assert_num_queries):
        from django.db.models import Count, Min

        from media.serializers import SeasonBriefSerializer

        show = TVShow.objects.create(tmdb_id=703, name='Query Show')
        for season_number in (1, 2, 3):
            season = show.seasons.create(
                tmdb_id=7030 + season_number, season_number=season_number, name=f'Season {season_number}'
            )
            season.episodes.create(tmdb_id=70300 + season_number * 10 + 1, episode_number=1, name='E1', air_date='2020-01-01')
            season.episodes.create(tmdb_id=70300 + season_number * 10 + 2, episode_number=2, name='E2', air_date='2020-01-08')

        seasons = show.seasons.order_by('season_number').annotate(
            actual_episode_count=Count('episodes'),
            computed_air_date=Min('episodes__air_date'),
        )
        with django_assert_num_queries(1):
            data = SeasonBriefSerializer(seasons, many=True).data

        assert [row['episode_count'] for row in data] == [2, 2, 2]
        assert str(data[0]['air_date']) == '2020-01-01'

    def test_movie_and_tv_detail_include_metadata_updated_at(self, auth_client):
        Movie.objects.create(tmdb_id=777, title='Movie Detail')
        show = TVShow.objects.create(tmdb_id=888, name='Show Detail', number_of_seasons=1, number_of_episodes=2)
        show.seasons.create(tmdb_id=8881, season_number=1, name='Season 1')

        movie_response = auth_client.get('/api/media/movies/777/')
        tv_response = auth_client.get('/api/media/tv/888/')

        assert movie_response.status_code == 200
        assert tv_response.status_code == 200
        assert 'metadata_updated_at' in movie_response.data
        assert 'metadata_updated_at' in tv_response.data

    def test_sync_movie_stores_original_title_and_language_name(self):
        def payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'El club de la lucha',
                    'original_title': 'Fight Club',
                    'original_language': 'en',
                    'spoken_languages': [
                        {'iso_639_1': 'en', 'english_name': 'English', 'name': 'English'},
                        {'iso_639_1': 'es', 'english_name': 'Spanish', 'name': 'Español'},
                    ],
                    'genres': [],
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=payload):
            movie = tmdb.sync_movie(550)

        assert movie.original_title == 'Fight Club'
        assert movie.language == 'en'
        assert movie.language_name == 'English'

    def test_sync_movie_leaves_language_name_empty_without_spoken_match(self):
        def payload(endpoint, params=None, **kwargs):
            if endpoint == '/movie/550':
                return {
                    'id': 550,
                    'title': 'Dark',
                    'original_title': 'Dark',
                    'original_language': 'de',
                    'spoken_languages': [],
                    'genres': [],
                }
            return {}

        with patch('media.tmdb.TMDBService._get', side_effect=payload) as mock_get:
            movie = tmdb.sync_movie(550)

        assert movie.language == 'de'
        assert movie.language_name == ''
        assert '/configuration/languages' not in [call.args[0] for call in mock_get.call_args_list]

    def test_sync_tv_show_stores_original_title_and_language_name(self):
        with patch.object(tmdb, 'get_tv_details', return_value={
            'id': 1399,
            'name': 'Juego de tronos',
            'original_name': 'Game of Thrones',
            'original_language': 'en',
            'spoken_languages': [
                {'iso_639_1': 'en', 'english_name': 'English', 'name': 'English'},
            ],
            'genres': [],
            'networks': [],
            'number_of_seasons': 0,
            'number_of_episodes': 0,
        }), patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])):
            show = tmdb.sync_tv_show(1399, recompute_user_statuses=False)

        assert show.original_title == 'Game of Thrones'
        assert show.language_name == 'English'

    def test_movie_and_tv_detail_expose_original_title_and_language_name(self, auth_client):
        Movie.objects.create(
            tmdb_id=777, title='El club de la lucha', original_title='Fight Club',
            language='en', language_name='English',
        )
        show = TVShow.objects.create(
            tmdb_id=888, name='Dark', original_title='Dark',
            language='de', language_name='German',
            number_of_seasons=1, number_of_episodes=1,
        )
        season = show.seasons.create(tmdb_id=8881, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=88811, episode_number=1, name='Ep 1')

        movie_response = auth_client.get('/api/media/movies/777/')
        tv_response = auth_client.get('/api/media/tv/888/')

        assert movie_response.data['original_title'] == 'Fight Club'
        assert movie_response.data['language_name'] == 'English'
        assert tv_response.data['original_title'] == 'Dark'
        assert tv_response.data['language_name'] == 'German'

    @staticmethod
    def _show_payload(tmdb_id, season_numbers):
        return {
            'id': tmdb_id,
            'name': f'Show {tmdb_id}',
            'first_air_date': '2020-01-01',
            'number_of_seasons': len(season_numbers),
            'genres': [],
            'networks': [],
            'seasons': [{'season_number': number} for number in season_numbers],
        }

    @staticmethod
    def _season_batch(tmdb_id, numbers, use_cache):
        return {
            number: {
                'id': tmdb_id * 100 + number,
                'name': f'Season {number}',
                'episodes': [{'id': tmdb_id * 1000 + number, 'episode_number': 1, 'name': 'Episode 1'}],
            }
            for number in numbers
        }

    def test_sync_tv_show_always_syncs_all_returned_seasons(self):
        with (
            patch.object(tmdb, 'get_tv_details', return_value=self._show_payload(555, [0, 1, 2])),
            patch.object(tmdb, '_fetch_season_batch', side_effect=self._season_batch) as mock_batch,
            patch.object(tmdb, 'get_season_external_ids', return_value={}),
            patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])),
        ):
            show = tmdb.sync_tv_show(555)

        mock_batch.assert_called_once_with(555, [0, 1, 2], True)
        assert sorted(show.seasons.values_list('season_number', flat=True)) == [0, 1, 2]
        assert Episode.objects.filter(season__show=show).count() == 3

    def test_sync_tv_show_refreshes_all_statuses_with_user(self, mocker, user):
        mock_refresh_statuses = mocker.patch('tracking.status_sync.refresh_all_statuses_for_show')
        with (
            patch.object(tmdb, 'get_tv_details', return_value=self._show_payload(556, [1])),
            patch.object(tmdb, '_fetch_season_batch', side_effect=self._season_batch),
            patch.object(tmdb, 'get_season_external_ids', return_value={}),
            patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])),
        ):
            tmdb.sync_tv_show(556, user_id=user.id)

        mock_refresh_statuses.assert_called_once_with(556, current_user_id=user.id)

    def test_sync_season_refreshes_episode_credits_after_upsert(self, mocker):
        mock_get_season = mocker.patch('media.tmdb.tmdb.get_season')
        mock_get_episode_credits = mocker.patch('media.tmdb.tmdb.get_episode_credits')
        show = TVShow.objects.create(tmdb_id=4242, name='Credits Show', number_of_seasons=1, number_of_episodes=1)
        mock_get_season.return_value = {
            'id': 424201,
            'season_number': 1,
            'name': 'Season 1',
            'air_date': '2024-01-01',
            'episode_count': 1,
            'episodes': [
                {
                    'id': 424211,
                    'episode_number': 1,
                    'name': 'Episode 1',
                    'air_date': '2024-01-02',
                    'runtime': 42,
                }
            ],
        }
        mock_get_episode_credits.return_value = {'cast': [{'name': 'Lead'}], 'crew': []}

        tmdb.sync_season(show, 1, sync_episode_credits=True)

        mock_get_episode_credits.assert_called_once_with(4242, 1, 1, use_cache=True)
        credit = EpisodeCredit.objects.get(episode__season__show=show)
        assert credit.cast == [{'name': 'Lead'}]

    def test_sync_season_persists_votes(self, mocker):
        mock_get_season = mocker.patch('media.tmdb.tmdb.get_season')
        show = TVShow.objects.create(tmdb_id=4343, name='Vote Show', number_of_seasons=1, number_of_episodes=1)
        mock_get_season.return_value = {
            'id': 434301,
            'season_number': 1,
            'name': 'Season 1',
            'vote_average': 8.4,
            'episodes': [],
        }

        season = tmdb.sync_season(show, 1)

        season.refresh_from_db()
        assert season.vote_average == 8.4
        assert season.vote_count == 0

    def test_season_credits_returns_aggregate_cast(self, mocker, auth_client):
        mock_credits = mocker.patch('media.views.tmdb.get_season_aggregate_credits')
        mock_credits.return_value = {
            'cast': [{'name': 'Season Regular', 'total_episode_count': 8}],
            'crew': [{'name': 'Season Director', 'job': 'Director'}],
        }

        response = auth_client.get('/api/media/tv/1399/seasons/1/credits/')

        assert response.status_code == 200
        assert response.data['cast'][0]['total_episode_count'] == 8
        assert response.data['crew'][0]['name'] == 'Season Director'
        assert 'guest_stars' not in response.data
        mock_credits.assert_called_once_with(1399, 1)

    def test_tv_credits_returns_whole_cast(self, mocker, auth_client):
        mock_credits = mocker.patch('media.views.tmdb.get_tv_aggregate_credits')
        mock_credits.return_value = {
            'cast': [
                {'name': 'Series Regular', 'total_episode_count': 10},
                {'name': 'One-Off', 'total_episode_count': 1},
            ],
            'crew': [{'name': 'Showrunner', 'job': 'Creator'}],
        }

        response = auth_client.get('/api/media/tv/1399/credits/')

        assert response.status_code == 200
        assert len(response.data['cast']) == 2
        assert response.data['crew'][0]['name'] == 'Showrunner'
        assert 'guest_stars' not in response.data
        mock_credits.assert_called_once_with(1399)

    def test_movie_recommendations_annotates_media_type_and_status(self, mocker, user, auth_client):
        mock_recs = mocker.patch('media.views.tmdb.get_movie_recommendations')
        mock_recs.return_value = {
            'page': 1,
            'results': [{'id': 551, 'title': 'Rec Movie', 'vote_average': 7.5}],
            'total_pages': 1,
            'total_results': 1,
        }
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=551, status='plan_to_watch')

        response = auth_client.get('/api/media/movies/550/recommendations/')

        assert response.status_code == 200
        assert response.data['results'][0]['media_type'] == 'movie'
        assert response.data['results'][0]['user_status']['status'] == 'plan_to_watch'

    def test_tv_recommendations_annotates_media_type(self, mocker, auth_client):
        mock_recs = mocker.patch('media.views.tmdb.get_tv_recommendations')
        mock_recs.return_value = {
            'page': 1,
            'results': [{'id': 1400, 'name': 'Rec Show', 'vote_average': 8.0}],
            'total_pages': 1,
            'total_results': 1,
        }

        response = auth_client.get('/api/media/tv/1399/recommendations/')

        assert response.status_code == 200
        assert response.data['results'][0]['media_type'] == 'tv'

    def test_collection_detail_annotates_parts(self, mocker, auth_client):
        mock_collection = mocker.patch('media.views.tmdb.get_collection')
        mock_collection.return_value = {
            'id': 10,
            'name': 'Test Collection',
            'overview': 'A collection',
            'parts': [{'id': 550, 'title': 'Fight Club'}],
        }

        response = auth_client.get('/api/media/collections/10/')

        assert response.status_code == 200
        assert response.data['name'] == 'Test Collection'
        assert response.data['parts'][0]['media_type'] == 'movie'

    def test_movie_external_ids_passthrough(self, mocker, auth_client):
        mock_details = mocker.patch('media.views.tmdb.get_movie_details')
        mock_details.return_value = {'external_ids': {'imdb_id': 'tt0137523', 'wikidata_id': 'Q42'}}

        response = auth_client.get('/api/media/movies/550/external-ids/')

        assert response.status_code == 200
        assert response.data['imdb_id'] == 'tt0137523'

    def test_tv_external_ids_returns_stored_ids(self, auth_client):
        TVShow.objects.create(tmdb_id=7777, name='Stored IDs', external_ids={'tvmaze_id': 123, 'imdb_id': 'tt1234567'})

        with patch('media.views.tmdb.get_tv_details', side_effect=Exception('offline')):
            response = auth_client.get('/api/media/tv/7777/external-ids/')

        assert response.status_code == 200
        assert response.data['tvmaze_id'] == 123

    def test_episode_external_ids_merges_stored_and_live(self, auth_client):
        show = TVShow.objects.create(tmdb_id=7778, name='Episode IDs')
        season = Season.objects.create(show=show, season_number=1, tmdb_id=1)
        Episode.objects.create(season=season, episode_number=2, tmdb_id=2, name='E2', external_ids={'tvmaze_id': 4953})

        with patch('media.views.tmdb.get_episode_external_ids', return_value={'imdb_id': 'tt1480055', 'tvdb_id': None}):
            response = auth_client.get('/api/media/tv/7778/seasons/1/episodes/2/external-ids/')
        assert response.status_code == 200
        assert response.data == {'tvmaze_id': 4953, 'imdb_id': 'tt1480055'}

        with patch('media.views.tmdb.get_episode_external_ids', side_effect=Exception('offline')):
            response = auth_client.get('/api/media/tv/7778/seasons/1/episodes/2/external-ids/')
        assert response.data == {'tvmaze_id': 4953}

        with patch('media.views.tmdb.get_episode_external_ids', side_effect=Exception('offline')):
            response = auth_client.get('/api/media/tv/7778/seasons/1/episodes/9/external-ids/')
        assert response.status_code == 404

    def test_movie_detail_includes_collection_and_external_ids(self, mocker, auth_client):
        mock_details = mocker.patch('media.views.tmdb.get_movie_details')
        from media.models import Movie
        Movie.objects.create(tmdb_id=999, title='Collection Movie')
        mock_details.return_value = {
            'id': 999,
            'belongs_to_collection': {'id': 10, 'name': 'Test Collection', 'poster_path': '/p.jpg', 'backdrop_path': '/b.jpg'},
            'external_ids': {'imdb_id': 'tt9999999'},
        }

        response = auth_client.get('/api/media/movies/999/')

        mock_details.assert_called_once_with(999)

        assert response.status_code == 200
        assert response.data['collection']['id'] == 10
        assert response.data['external_ids']['imdb_id'] == 'tt9999999'

    def test_season_detail_includes_overview_credits_and_cast(self, mocker, auth_client):
        mock_season = mocker.patch('media.views.tmdb.get_season')
        show = TVShow.objects.create(tmdb_id=707, name='Season Extras', number_of_seasons=1, number_of_episodes=1, external_ids={'imdb_id': 'tt0000707'})
        season = show.seasons.create(tmdb_id=7070, season_number=1, name='Season 1', overview='Season overview')
        episode = season.episodes.create(tmdb_id=70701, episode_number=1, name='Ep 1', external_ids={'tvmaze_id': 55})
        EpisodeCredit.objects.create(episode=episode, cast=[{'name': 'Ep Cast'}], crew=[], guest_stars=[])
        mock_season.return_value = {
            'vote_average': 8.4,
            'vote_count': 42,
            'credits': {'cast': [{'name': 'Season Cast'}], 'crew': []},
            'external_ids': {'tvdb_id': 123},
        }

        response = auth_client.get('/api/media/tv/707/seasons/1/')

        assert response.status_code == 200
        assert response.data['show_name'] == 'Season Extras'
        assert response.data['vote_average'] == 8.4
        assert response.data['vote_count'] == 42
        assert response.data['overview'] == 'Season overview'
        assert response.data['credits']['cast'][0]['name'] == 'Season Cast'
        assert response.data['episodes'][0]['cast'][0]['name'] == 'Ep Cast'
        assert response.data['episodes'][0]['external_ids'] == {'tvmaze_id': 55}
        assert response.data['show_external_ids'] == {'imdb_id': 'tt0000707'}

    def test_tv_brief_includes_season_overview(self, auth_client):
        show = TVShow.objects.create(tmdb_id=708, name='Brief Overview', number_of_seasons=1, number_of_episodes=1)
        season = show.seasons.create(tmdb_id=7080, season_number=1, name='Season 1', overview='Brief season overview')
        season.vote_average = 8.1
        season.vote_count = 15
        season.save(update_fields=['vote_average', 'vote_count'])

        with patch('media.views.tmdb.get_tv_details', return_value={}):
            response = auth_client.get('/api/media/tv/708/')

        assert response.status_code == 200
        assert response.data['seasons'][0]['overview'] == 'Brief season overview'
        assert response.data['seasons'][0]['vote_average'] == 8.1
        assert response.data['seasons'][0]['vote_count'] == 15
        assert 'external_ids' in response.data

    def test_person_detail_merges_external_ids_and_profile_url(self, mocker, auth_client):
        mock_person = mocker.patch('media.views.tmdb.get_person')
        mock_ids = mocker.patch('media.views.tmdb.get_person_external_ids')
        mock_person.return_value = {
            'id': 123,
            'name': 'Test Actor',
            'biography': 'A biography',
            'profile_path': '/actor.jpg',
            'also_known_as': ['T. Actor'],
            'gender': 2,
            'birthday': '1965-09-17',
            'place_of_birth': 'Buffalo, New York, USA',
            'known_for_department': 'Acting',
        }
        mock_ids.return_value = {'imdb_id': 'nm1234567'}

        response = auth_client.get('/api/media/people/123/')

        assert response.status_code == 200
        assert response.data['name'] == 'Test Actor'
        assert response.data['external_ids']['imdb_id'] == 'nm1234567'
        assert response.data['profile_url'] == 'https://image.tmdb.org/t/p/w500/actor.jpg'
        assert response.data['also_known_as'] == ['T. Actor']
        assert response.data['gender'] == 2

    def test_person_credits_returns_cast_and_crew(self, mocker, auth_client):
        mock_credits = mocker.patch('media.views.tmdb.get_person_combined_credits')
        mock_credits.return_value = {
            'cast': [{'id': 550, 'media_type': 'movie', 'title': 'Fight Club'}],
            'crew': [{
                'id': 1399,
                'media_type': 'tv',
                'name': 'Show',
                'first_credit_air_date': '2014-05-11',
            }],
        }

        response = auth_client.get('/api/media/people/123/credits/')

        assert response.status_code == 200
        assert len(response.data['cast']) == 1
        assert len(response.data['crew']) == 1
        assert response.data['cast'][0]['media_type'] == 'movie'
        assert response.data['crew'][0]['media_type'] == 'tv'
        assert response.data['crew'][0]['first_credit_air_date'] == '2014-05-11'

    def test_person_detail_returns_404_when_missing(self, mocker, auth_client):
        mock_person = mocker.patch('media.views.tmdb.get_person')
        mock_person.return_value = {}

        response = auth_client.get('/api/media/people/999999/')

        assert response.status_code == 404

    def test_person_endpoints_require_authentication(self, mocker):
        mock_person = mocker.patch('media.views.tmdb.get_person')
        anon = APIClient()
        mock_person.return_value = {'id': 123, 'name': 'Test Actor'}

        assert anon.get('/api/media/people/123/').status_code == 401
        assert anon.get('/api/media/people/123/credits/').status_code == 401
        assert anon.get('/api/media/people/123/external-ids/').status_code == 401

    def test_people_search_returns_results(self, mocker, auth_client):
        mock_search = mocker.patch('media.views.tmdb.search_people')
        mock_search.return_value = {
            'results': [{'id': 123, 'name': 'Test Actor', 'known_for_department': 'Acting'}],
            'page': 1,
            'total_pages': 1,
            'total_results': 1,
        }

        response = auth_client.get('/api/media/people/search/?q=test')

        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Test Actor'
        mock_search.assert_called_once_with('test', 1)

    def test_people_search_returns_empty_without_query(self, auth_client):
        response = auth_client.get('/api/media/people/search/')

        assert response.status_code == 200
        assert response.data['results'] == []

    def test_people_search_returns_empty_on_tmdb_error(self, mocker, auth_client):
        mock_search = mocker.patch('media.views.tmdb.search_people')
        mock_search.side_effect = Exception('TMDB offline')

        response = auth_client.get('/api/media/people/search/?q=test')

        assert response.status_code == 200
        assert response.data['results'] == []

    def test_people_search_requires_authentication(self):
        anon = APIClient()

        assert anon.get('/api/media/people/search/?q=test').status_code == 401


class SeasonDetailQueryCountTests:
    def test_season_detail_does_not_query_per_episode(self):
        from media.models import EpisodeCredit

        user = User.objects.create_user(username='seasonq', password='testpass123')
        client = APIClient()
        client.force_authenticate(user)

        def query_count(episodes):
            show = TVShow.objects.create(tmdb_id=600 + episodes, name='Show', number_of_seasons=1)
            season = Season.objects.create(show=show, tmdb_id=650 + episodes, season_number=1, name='Season 1')
            for number in range(1, episodes + 1):
                episode = Episode.objects.create(season=season, tmdb_id=10000 * episodes + number, episode_number=number, name=f'E{number}')
                EpisodeCredit.objects.create(episode=episode, cast=[], crew=[], guest_stars=[])
            with CaptureQueriesContext(connection) as ctx:
                assert client.get(f'/api/media/tv/{show.tmdb_id}/seasons/1/').status_code == 200
            return len(ctx.captured_queries)

        assert query_count(10) == query_count(2)


class EpisodeCreditsQueueTests:
    def test_identical_credit_syncs_are_queued_once(self, mocker):
        mock_task = mocker.patch('media.views.sync_show_episode_credits')
        from media.views import _queue_episode_credits_sync

        for _ in range(3):
            _queue_episode_credits_sync(1399, season_numbers=[2], use_cache=True)
        _queue_episode_credits_sync(1399, season_numbers=[3], use_cache=True)
        _queue_episode_credits_sync(1399, use_cache=False)

        assert [call.args for call in mock_task.delay.call_args_list] == [(1399, [2], True), (1399, [3], True), (1399, None, False)]

    def test_queues_when_the_cache_is_unavailable(self, mocker):
        mock_task = mocker.patch('media.views.sync_show_episode_credits')
        from media.views import _queue_episode_credits_sync

        with patch('media.views.cache.add', return_value=None):
            _queue_episode_credits_sync(1399, season_numbers=[1])
            _queue_episode_credits_sync(1399, season_numbers=[1])

        assert mock_task.delay.call_count == 2


class MediaViewTransactionTests:
    def test_media_views_do_not_wrap_tmdb_calls_in_a_request_transaction(self, auth_client):
        baseline = len(connection.atomic_blocks)
        depths = []

        def capture(*args, **kwargs):
            depths.append(len(connection.atomic_blocks))
            return {'results': []}

        with patch.object(tmdb, 'get_trending', side_effect=capture):
            auth_client.get('/api/media/trending/', {'type': 'movie'})

        assert depths == [baseline]


@pytest.mark.unfaked_tmdb_get
class TMDBUseCacheTests:
    def test_get_does_not_retry_after_request_timeout(self):
        with patch.object(tmdb._session, 'get', side_effect=requests.Timeout('TMDB timed out')) as mock_requests_get, patch('media.tmdb.time.sleep') as mock_sleep, pytest.raises(requests.Timeout):
            tmdb._get('/movie/550', use_cache=False)

        mock_requests_get.assert_called_once()
        mock_sleep.assert_not_called()

    def test_get_without_cache_skips_read_and_overwrites_cached_entry(self):
        payload = {'id': 550, 'title': 'Fresh Movie'}
        mock_response = MagicMock()
        mock_response.json.return_value = payload

        params = {'append_to_response': 'credits,videos'}
        key = response_cache_key('tmdb', '/movie/550', params)
        django_cache.set(key, {'title': 'Stale Movie'})

        with patch.object(tmdb._session, 'get', return_value=mock_response) as mock_requests_get:
            result = tmdb._get('/movie/550', params, use_cache=False)

        assert result == payload
        assert mock_requests_get.call_args.kwargs['timeout'] == tmdb.REQUEST_TIMEOUT
        assert django_cache.get(key) == payload

    def test_get_with_cache_returns_cached_payload_without_network_call(self):
        cached_payload = {'id': 550, 'title': 'Cached Movie'}

        params = {'append_to_response': 'credits,videos'}
        django_cache.set(response_cache_key('tmdb', '/movie/550', params), cached_payload)

        with patch.object(tmdb._session, 'get') as mock_requests_get:
            result = tmdb._get('/movie/550', params, use_cache=True)

        assert result == cached_payload
        mock_requests_get.assert_not_called()

    def test_get_survives_unreachable_redis(self):
        payload = {'id': 550, 'title': 'Live Movie'}
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        unreachable = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': 'redis://127.0.0.1:1/0',
                'OPTIONS': {'IGNORE_EXCEPTIONS': True, 'SOCKET_CONNECT_TIMEOUT': 0.2, 'SOCKET_TIMEOUT': 0.2},
            },
        }

        with override_settings(CACHES=unreachable), \
                patch.object(tmdb._session, 'get', return_value=mock_response) as mock_requests_get:
            assert tmdb._get('/movie/550') == payload
            assert tmdb._get('/movie/550') == payload

        assert mock_requests_get.call_count == 2

    def test_sync_tv_show_propagates_use_cache_false(self, mocker):
        mocker.patch('tracking.status_sync.refresh_all_statuses_for_show')
        show_payload = {
            'id': 557,
            'name': 'No Cache Show',
            'first_air_date': '2020-01-01',
            'number_of_seasons': 1,
            'genres': [],
            'networks': [],
            'seasons': [{'season_number': 1}],
        }
        with (
            patch.object(tmdb, 'get_tv_details', return_value=show_payload) as mock_details,
            patch.object(tmdb, '_fetch_season_batch', return_value={1: {'id': 5571, 'episodes': []}}) as mock_batch,
            patch.object(tmdb, 'get_season_external_ids', return_value={}),
            patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])),
        ):
            show = tmdb.sync_tv_show(557, use_cache=False)

        assert show.tmdb_id == 557
        mock_details.assert_called_once_with(557, use_cache=False)
        mock_batch.assert_called_once_with(557, [1], False)

    def test_sync_movie_propagates_use_cache_false(self, mocker):
        mock_get_movie = mocker.patch('media.tmdb.tmdb.get_movie_details')
        mock_get_movie.return_value = {
            'id': 551,
            'title': 'No Cache Movie',
            'overview': 'cache bypass test',
            'release_date': '2020-01-01',
            'genres': [],
        }

        movie = tmdb.sync_movie(551, use_cache=False)

        assert movie.tmdb_id == 551
        mock_get_movie.assert_called_once_with(551, use_cache=False)


class TMDBFetchTests:
    @staticmethod
    def _server_error():
        response = requests.Response()
        response.status_code = 500
        return requests.HTTPError('500 Server Error', response=response)

    def test_movie_detail_cold_load_uses_one_tmdb_resource(self):
        user = User.objects.create_user(username='fetcher', password='testpass123')
        client = APIClient()
        client.force_authenticate(user=user)
        requested = []

        def fake_get(endpoint, params=None, **kwargs):
            requested.append((endpoint, json.dumps(params, sort_keys=True)))
            return {
                'id': 560,
                'title': 'Bundled Movie',
                'belongs_to_collection': {'id': 7, 'name': 'Saga'},
                'external_ids': {'imdb_id': 'tt0000560'},
                'watch/providers': {'results': {'US': {'link': 'https://example.com'}}},
                'keywords': {'keywords': []},
            }

        with patch.object(tmdb, '_get', side_effect=fake_get):
            response = client.get('/api/media/movies/560/')

        assert response.status_code == 200
        assert response.data['collection']['id'] == 7
        assert response.data['external_ids'] == {'imdb_id': 'tt0000560'}
        assert response.data['watch_providers']['region'] == 'US'
        # sync and view share one cache key, so Redis answers the second read.
        assert set(requested) == {(
            '/movie/560',
            json.dumps({'append_to_response': 'keywords,external_ids,watch/providers'}, sort_keys=True),
        )}

    def test_tv_details_bundles_external_ids_and_providers(self):
        with patch.object(tmdb, '_get', return_value={}) as mock_get:
            tmdb.get_tv_details(1399)

        mock_get.assert_called_once_with(
            '/tv/1399', {'append_to_response': 'external_ids,watch/providers'}, use_cache=True
        )

    def test_fetch_seasons_bundles_twenty_seasons_per_request(self):
        requested = []

        def fake_get(endpoint, params=None, **kwargs):
            appends = params['append_to_response'].split(',')
            requested.append(appends)
            return {append: {'name': append, 'episodes': []} for append in appends}

        with patch.object(tmdb, '_get', side_effect=fake_get):
            seasons, _ = tmdb._fetch_seasons_with(1399, list(range(1, 46)), True, [])

        assert sorted(len(appends) for appends in requested) == [5, 20, 20]
        assert sorted(seasons) == list(range(1, 46))

    def test_fetch_seasons_merges_season_summary_into_payload(self):
        response = {
            'seasons': [{'id': 180379, 'season_number': 1, 'episode_count': 10}],
            'season/1': {'season_number': 1, 'name': 'Season 1', 'episodes': []},
        }
        with patch.object(tmdb, '_get', return_value=response):
            seasons, _ = tmdb._fetch_seasons_with(118357, [1], True, [])

        assert seasons[1]['id'] == 180379
        assert seasons[1]['episode_count'] == 10
        assert seasons[1]['name'] == 'Season 1'

    def test_poisoned_append_is_isolated_and_the_rest_still_fetched(self):
        def fake_get(endpoint, params=None, **kwargs):
            appends = (params or {}).get('append_to_response', '').split(',')
            if 'season/3' in appends:
                raise self._server_error()
            return {append: {'name': append, 'episodes': []} for append in appends if append}

        with patch.object(tmdb, '_get', side_effect=fake_get):
            data = tmdb._get_appended('/tv/1', [f'season/{n}' for n in range(1, 5)])

        assert sorted(data) == ['season/1', 'season/2', 'season/4']

    def test_seasons_missing_from_batches_fall_back_to_single_requests(self):
        def fake_get(endpoint, params=None, **kwargs):
            if endpoint == '/tv/1/season/2':
                return {'name': 'Season 2', 'episodes': []}
            return {'season/1': {'name': 'Season 1', 'episodes': []}}

        with patch.object(tmdb, '_get', side_effect=fake_get) as mock_get:
            seasons, _ = tmdb._fetch_seasons_with(1, [1, 2], True, [])

        assert sorted(seasons) == [1, 2]
        assert mock_get.call_count == 2

    def test_parallel_requests_are_capped_at_eight_and_failures_are_isolated(self):
        import threading
        import time as time_module

        from media.http import MAX_WORKERS, run_parallel

        lock = threading.Lock()
        state = {'active': 0, 'peak': 0}

        def call(index):
            with lock:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
            time_module.sleep(0.02)
            with lock:
                state['active'] -= 1
            if index == 3:
                raise ValueError('boom')
            return index

        results = run_parallel([lambda index=index: call(index) for index in range(20)])

        assert MAX_WORKERS == 8
        assert state['peak'] == 8
        assert isinstance(results[3], ValueError)
        assert [r for r in results if not isinstance(r, Exception)] == [i for i in range(20) if i != 3]

    def test_season_upsert_query_count_does_not_scale_with_episodes(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        show = TVShow.objects.create(tmdb_id=880, name='Bulk Show')

        def payload(count):
            return {
                'id': 8801,
                'name': 'Season 1',
                'episodes': [{'id': 88000 + n, 'episode_number': n, 'name': f'E{n}'} for n in range(1, count + 1)],
            }

        tmdb._upsert_season(show, 1, payload(40), tvmaze_show=None, tvmaze_episodes=[])
        with CaptureQueriesContext(connection) as queries:
            tmdb._upsert_season(show, 1, payload(60), tvmaze_show=None, tvmaze_episodes=[])

        assert Episode.objects.filter(season__show=show).count() == 60
        assert len(queries) < 12

    def test_sync_show_episode_credits_fetches_in_parallel_and_saves_in_bulk(self):
        show = TVShow.objects.create(tmdb_id=881, name='Credits Bulk Show')
        season = show.seasons.create(tmdb_id=8811, season_number=1, name='Season 1')
        for number in range(1, 6):
            season.episodes.create(tmdb_id=88110 + number, episode_number=number, name=f'E{number}')
        existing = season.episodes.get(episode_number=1)
        EpisodeCredit.objects.create(episode=existing, cast=[{'name': 'Kept'}], crew=[], guest_stars=[])

        def fake_credits(show_id, season_number, episode_number, *, use_cache=True):
            if episode_number == 5:
                raise self._server_error()
            return {'cast': [] if episode_number == 1 else [{'name': f'Cast {episode_number}'}], 'crew': []}

        with patch.object(tmdb, 'get_episode_credits', side_effect=fake_credits):
            synced, failures = tmdb.sync_show_episode_credits(show)

        assert (synced, failures) == (4, 1)
        assert EpisodeCredit.objects.filter(episode__season=season).count() == 4
        assert EpisodeCredit.objects.get(episode=existing).cast == [{'name': 'Kept'}]


class RemovedEpisodeCleanupTests:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.user = User.objects.create_user(username='cleaner', password='testpass123')
        self.show = TVShow.objects.create(tmdb_id=950, name='Shrinking Show')
        self.season = self.show.seasons.create(tmdb_id=9501, season_number=1, name='Season 1')
        for number in (1, 2, 3):
            self.season.episodes.create(tmdb_id=95000 + number, episode_number=number, name=f'E{number}')

    def _upsert(self, numbers):
        payload = {
            'id': 9501,
            'name': 'Season 1',
            'episodes': [{'id': 95000 + n, 'episode_number': n, 'name': f'E{n}'} for n in numbers],
        }
        with patch('tracking.tasks.system.cleanup_removed_episodes.delay') as mock_delay, TestCase.captureOnCommitCallbacks(execute=True):
            tmdb._upsert_season(self.show, 1, payload, tvmaze_show=None, tvmaze_episodes=[])
        return mock_delay

    def test_removed_episode_queues_cleanup(self):
        mock_delay = self._upsert([1, 2])

        mock_delay.assert_called_once_with(950, 1, [3])

    def test_swapped_episode_is_detected_even_when_count_is_unchanged(self):
        mock_delay = self._upsert([1, 2, 4])

        mock_delay.assert_called_once_with(950, 1, [3])

    def test_empty_season_payload_never_queues_cleanup(self):
        mock_delay = self._upsert([])

        mock_delay.assert_not_called()
        assert self.season.episodes.count() == 3

    def test_failed_season_fetch_never_queues_cleanup(self):
        with patch.object(tmdb, 'get_tv_details', return_value={'id': 950, 'name': 'Shrinking Show', 'seasons': [{'season_number': 1}]}), patch.object(tmdb, '_fetch_season_batch', side_effect=RuntimeError('down')), patch.object(tmdb, 'get_season', side_effect=RuntimeError('down')), patch.object(tmdb, '_resolve_tvmaze', return_value=(None, [])), patch('tracking.tasks.system.cleanup_removed_episodes.delay') as mock_delay, TestCase.captureOnCommitCallbacks(execute=True):
            tmdb.sync_tv_show(950, recompute_user_statuses=False)

        mock_delay.assert_not_called()
        assert self.season.episodes.count() == 3

    def test_cleanup_deletes_unwatched_and_keeps_watched_episodes(self, mocker, user):
        mock_refresh = mocker.patch('tracking.tasks.system.refresh_all_statuses_for_show')
        from tracking.tasks.system import cleanup_removed_episodes

        WatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=950, season_number=1, episode_number=2,
        )
        EpisodeCredit.objects.create(episode=self.season.episodes.get(episode_number=3), cast=[], crew=[], guest_stars=[])

        result = cleanup_removed_episodes(950, 1, [2, 3])

        assert result['deleted'] == 1
        assert result['kept'] == [2]
        assert sorted(self.season.episodes.values_list('episode_number', flat=True)) == [1, 2]
        assert not EpisodeCredit.objects.filter(episode__season=self.season).exists()
        mock_refresh.assert_called_once_with(950)

    def test_cleanup_is_idempotent(self, mocker):
        mock_refresh = mocker.patch('tracking.tasks.system.refresh_all_statuses_for_show')
        from tracking.tasks.system import cleanup_removed_episodes

        cleanup_removed_episodes(950, 1, [3])
        result = cleanup_removed_episodes(950, 1, [3])

        assert result['deleted'] == 0
        assert self.season.episodes.count() == 2
        mock_refresh.assert_called_once_with(950)
