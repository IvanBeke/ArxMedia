import pytest
import requests
from django.urls import reverse

from integrations.clients import jellyfin_client
from media.http import MAX_WORKERS
from media.models import Episode, Season, TVShow

SHOW_LINKS_URL = reverse('jellyfin_show_links', args=[1396])
MOVIE_LINK_URL = reverse('jellyfin_movie_link', args=[603])
EPISODE_LINKS_URL = reverse('jellyfin_episode_links')
PAGE = 'http://jellyfin.test:8096/web/index.html#/details'

SERIES = {'Items': [
    {'Id': 'series-bb', 'ServerId': 'srv', 'ProviderIds': {'Tmdb': '1396', 'Tvdb': '81189'}},
    {'Id': 'series-no-tmdb', 'ServerId': 'srv', 'ProviderIds': {'Imdb': 'tt1'}},
    {'Id': 'series-other', 'ServerId': 'srv', 'ProviderIds': {'Tmdb': '1399'}},
]}
MOVIES = {'Items': [
    {'Id': 'movie-matrix', 'ServerId': 'srv', 'ProviderIds': {'Tmdb': '603', 'Imdb': 'tt0133093'}},
    {'Id': 'movie-no-tmdb', 'ServerId': 'srv', 'ProviderIds': {'Imdb': 'tt2'}},
]}
SEASONS = {'Items': [
    {'Id': 'season-0', 'ServerId': 'srv', 'IndexNumber': 0},
    {'Id': 'season-1', 'ServerId': 'srv', 'IndexNumber': 1},
    {'Id': 'season-2', 'ServerId': 'srv', 'IndexNumber': 2},
]}
EPISODES = {'Items': [
    {'Id': 'ep-1-1', 'ServerId': 'srv', 'SeasonId': 'season-1', 'ParentIndexNumber': 1, 'IndexNumber': 1, 'ProviderIds': {'Tvdb': '101'}},
    {'Id': 'ep-1-2', 'ServerId': 'srv', 'SeasonId': 'season-1', 'ParentIndexNumber': 1, 'IndexNumber': 2, 'ProviderIds': {'Tvdb': '102'}},
    {'Id': 'ep-2-1', 'ServerId': 'srv', 'SeasonId': 'season-2', 'ParentIndexNumber': 2, 'IndexNumber': 1, 'ProviderIds': {'Tvdb': '201'}},
    {'Id': 'ep-2-2', 'ServerId': 'srv', 'SeasonId': 'season-2', 'ParentIndexNumber': 2, 'IndexNumber': 2, 'ProviderIds': {'Tvdb': '202'}},
]}
# TMDB puts the TVDB second season's episodes in its first season, after E2
TMDB_TVDB_IDS = {(1396, 1, 3): 201, (1396, 1, 4): 202, (1396, 5, 1): 201}
NO_LINKS = {'show_url': None, 'season_url': None, 'episode_url': None}


@pytest.fixture
def library(fake_arr):
    fake_arr.on('GET', '/Items', lambda params: MOVIES if params['includeItemTypes'] == 'Movie' else SERIES)
    fake_arr.on('GET', '/Shows/series-bb/Seasons', SEASONS)
    fake_arr.on('GET', '/Shows/series-bb/Episodes', EPISODES)
    return fake_arr


@pytest.fixture(autouse=True)
def tmdb_episode_ids(mocker):
    def fetch(show_id, season, episode, *, use_cache=True):
        return {'tvdb_id': TMDB_TVDB_IDS.get((show_id, season, episode)), 'imdb_id': None}

    return mocker.patch('media.tmdb.tmdb.get_episode_external_ids', side_effect=fetch)


class TestPermissionGate:
    def test_anonymous_gets_401(self, api_client, jellyfin_settings):
        assert api_client.get(SHOW_LINKS_URL).status_code == 401
        assert api_client.post(EPISODE_LINKS_URL, {'items': []}, format='json').status_code == 401

    def test_user_without_permission_gets_403(self, auth_client, jellyfin_settings):
        assert auth_client.get(SHOW_LINKS_URL).status_code == 403
        assert auth_client.post(EPISODE_LINKS_URL, {'items': []}, format='json').status_code == 403

    def test_sonarr_radarr_permission_does_not_grant_access(self, arr_client, jellyfin_settings):
        assert arr_client.get(SHOW_LINKS_URL).status_code == 403

    def test_superuser_is_allowed(self, api_client, user, jellyfin_settings, library):
        user.is_superuser = True
        user.save()
        api_client.force_authenticate(user=user)

        assert api_client.get(SHOW_LINKS_URL).status_code == 200


class TestUnconfigured:
    def test_returns_503_when_jellyfin_is_not_configured(self, api_client, jellyfin_user, settings):
        settings.JELLYFIN_URL = ''
        settings.JELLYFIN_API_KEY = ''
        api_client.force_authenticate(user=jellyfin_user)

        for response in (
            api_client.get(SHOW_LINKS_URL),
            api_client.post(EPISODE_LINKS_URL, {'items': []}, format='json'),
        ):
            assert response.status_code == 503
            assert response.data['detail'] == 'Jellyfin is not configured.'


class TestShowLinks:
    def test_returns_the_show_link_using_the_tmdb_id(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL)

        assert response.status_code == 200
        assert response.data == {**NO_LINKS, 'show_url': f'{PAGE}?id=series-bb&serverId=srv'}
        first = library.calls[0]
        assert first['url'] == 'http://jellyfin.test:8096/Items'
        assert first['headers']['Authorization'] == 'MediaBrowser Token="jellyfin-key"'
        assert first['params']['includeItemTypes'] == 'Series'
        assert first['params']['fields'] == 'ProviderIds'

    def test_returns_the_season_link(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 1})

        assert response.data == {
            'show_url': f'{PAGE}?id=series-bb&serverId=srv',
            'season_url': f'{PAGE}?id=season-1&serverId=srv',
            'episode_url': None,
        }

    def test_returns_the_specials_season(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 0})

        assert response.data['season_url'] == f'{PAGE}?id=season-0&serverId=srv'

    def test_returns_the_episode_link(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 2})

        assert response.data == {
            'show_url': f'{PAGE}?id=series-bb&serverId=srv',
            'season_url': f'{PAGE}?id=season-1&serverId=srv',
            'episode_url': f'{PAGE}?id=ep-1-2&serverId=srv',
        }
        assert 'season' not in library.calls_to('GET', '/Shows/series-bb/Episodes')[0]['params']

    def test_missing_season_and_episode_have_no_link(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 9, 'episode': 1})

        assert response.data == {**NO_LINKS, 'show_url': f'{PAGE}?id=series-bb&serverId=srv'}

    def test_missing_episode_has_no_link(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 9})

        assert response.data['season_url'] is not None
        assert response.data['episode_url'] is None

    def test_show_missing_from_the_library_has_no_links(self, jellyfin_api, library):
        response = jellyfin_api.get(reverse('jellyfin_show_links', args=[999]), {'season': 1, 'episode': 1})

        assert response.status_code == 200
        assert response.data == NO_LINKS

    def test_links_use_the_public_url_when_set(self, jellyfin_api, jellyfin_settings, library):
        jellyfin_settings.JELLYFIN_PUBLIC_URL = 'https://jellyfin.example.com/media'

        response = jellyfin_api.get(SHOW_LINKS_URL)

        assert response.data['show_url'] == 'https://jellyfin.example.com/media/web/index.html#/details?id=series-bb&serverId=srv'
        assert library.calls[0]['host'] == 'jellyfin.test:8096'

    def test_link_omits_the_server_id_when_jellyfin_gives_none(self, jellyfin_api, fake_arr):
        fake_arr.on('GET', '/Items', {'Items': [{'Id': 'series-bb', 'ProviderIds': {'Tmdb': '1396'}}]})

        response = jellyfin_api.get(SHOW_LINKS_URL)

        assert response.data['show_url'] == f'{PAGE}?id=series-bb'

    def test_rejects_invalid_query_values(self, jellyfin_api, library):
        assert jellyfin_api.get(SHOW_LINKS_URL, {'season': -1}).status_code == 400
        assert jellyfin_api.get(SHOW_LINKS_URL, {'season': 'one'}).status_code == 400
        assert jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 0}).status_code == 400

    def test_library_lookups_are_cached_between_requests(self, jellyfin_api, library):
        jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 1})
        jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 2})
        jellyfin_api.get(SHOW_LINKS_URL, {'season': 1})
        jellyfin_api.get(SHOW_LINKS_URL, {'season': 1})

        assert len(library.calls_to('GET', '/Items')) == 1
        assert len(library.calls_to('GET', '/Shows/series-bb/Episodes')) == 1
        assert len(library.calls_to('GET', '/Shows/series-bb/Seasons')) == 1

    def test_a_season_link_needs_no_episode_lookup(self, jellyfin_api, library):
        jellyfin_api.get(SHOW_LINKS_URL, {'season': 1})

        assert library.calls_to('GET', '/Shows/series-bb/Episodes') == []


class TestMovieLink:
    def test_returns_the_movie_link_using_the_tmdb_id(self, jellyfin_api, library):
        response = jellyfin_api.get(MOVIE_LINK_URL)

        assert response.status_code == 200
        assert response.data == {'url': f'{PAGE}?id=movie-matrix&serverId=srv'}
        assert library.calls[0]['params']['includeItemTypes'] == 'Movie'

    def test_movie_missing_from_the_library_has_no_link(self, jellyfin_api, library):
        response = jellyfin_api.get(reverse('jellyfin_movie_link', args=[999]))

        assert response.status_code == 200
        assert response.data == {'url': None}

    def test_requires_the_jellyfin_permission(self, auth_client, arr_client, jellyfin_settings):
        assert auth_client.get(MOVIE_LINK_URL).status_code == 403
        assert arr_client.get(MOVIE_LINK_URL).status_code == 403

    def test_anonymous_gets_401(self, api_client, jellyfin_settings):
        assert api_client.get(MOVIE_LINK_URL).status_code == 401

    def test_returns_503_when_jellyfin_is_not_configured(self, api_client, jellyfin_user, settings):
        settings.JELLYFIN_URL = ''
        settings.JELLYFIN_API_KEY = ''
        api_client.force_authenticate(user=jellyfin_user)

        assert api_client.get(MOVIE_LINK_URL).status_code == 503

    def test_the_movie_library_is_cached_separately_from_the_series_library(self, jellyfin_api, library):
        jellyfin_api.get(MOVIE_LINK_URL)
        jellyfin_api.get(MOVIE_LINK_URL)
        jellyfin_api.get(SHOW_LINKS_URL)

        assert [call['params']['includeItemTypes'] for call in library.calls_to('GET', '/Items')] == ['Movie', 'Series']

    def test_degrades_to_no_link_when_jellyfin_is_unreachable(self, jellyfin_api, mocker):
        mocker.patch('requests.Session.request', side_effect=requests.ConnectionError('refused'))

        response = jellyfin_api.get(MOVIE_LINK_URL)

        assert response.status_code == 200
        assert response.data == {'url': None}


class TestEpisodeLinks:
    def post(self, client, *items):
        return client.post(EPISODE_LINKS_URL, {'items': list(items)}, format='json')

    def test_returns_a_link_per_requested_episode_in_order(self, jellyfin_api, library):
        response = self.post(
            jellyfin_api,
            {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 2},
            {'tmdb_id': 999, 'season_number': 1, 'episode_number': 1},
            {'tmdb_id': 1396, 'season_number': 2, 'episode_number': 1},
            {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 9},
        )

        assert response.status_code == 200
        assert response.data['results'] == [
            {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 2, 'url': f'{PAGE}?id=ep-1-2&serverId=srv'},
            {'tmdb_id': 999, 'season_number': 1, 'episode_number': 1, 'url': None},
            {'tmdb_id': 1396, 'season_number': 2, 'episode_number': 1, 'url': f'{PAGE}?id=ep-2-1&serverId=srv'},
            {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 9, 'url': None},
        ]

    def test_fetches_each_series_only_once(self, jellyfin_api, library):
        self.post(
            jellyfin_api,
            {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 1},
            {'tmdb_id': 1396, 'season_number': 2, 'episode_number': 1},
        )

        assert len(library.calls_to('GET', '/Items')) == 1
        assert len(library.calls_to('GET', '/Shows/series-bb/Episodes')) == 1

    def test_an_empty_list_needs_no_lookups(self, jellyfin_api, library):
        response = self.post(jellyfin_api)

        assert response.status_code == 200
        assert response.data['results'] == []

    def test_rejects_invalid_items(self, jellyfin_api, library):
        assert self.post(jellyfin_api, {'tmdb_id': 1396}).status_code == 400
        assert self.post(jellyfin_api, {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 0}).status_code == 400
        too_many = [{'tmdb_id': 1396, 'season_number': 1, 'episode_number': 1}] * 51
        assert self.post(jellyfin_api, *too_many).status_code == 400


class TestTvdbEpisodeMatching:
    def post(self, client, *refs):
        items = [{'tmdb_id': tmdb_id, 'season_number': season, 'episode_number': episode} for tmdb_id, season, episode in refs]
        return client.post(EPISODE_LINKS_URL, {'items': items}, format='json')

    @pytest.fixture
    def stored_episode(self):
        show = TVShow.objects.create(tmdb_id=1396, name='Breaking Bad')
        season = Season.objects.create(show=show, season_number=1, tmdb_id=1)
        return Episode.objects.create(season=season, episode_number=3, tmdb_id=3, name='E3', external_ids={'tvmaze_id': 9})

    def test_an_episode_missing_by_number_is_matched_by_its_tvdb_id(self, jellyfin_api, library):
        response = self.post(jellyfin_api, (1396, 1, 3), (1396, 1, 4))

        assert [result['url'] for result in response.data['results']] == [
            f'{PAGE}?id=ep-2-1&serverId=srv', f'{PAGE}?id=ep-2-2&serverId=srv',
        ]

    def test_show_links_match_the_episode_and_link_its_season(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 3})

        assert response.data == {
            'show_url': f'{PAGE}?id=series-bb&serverId=srv',
            'season_url': f'{PAGE}?id=season-2&serverId=srv',
            'episode_url': f'{PAGE}?id=ep-2-1&serverId=srv',
        }

    def test_a_season_missing_in_jellyfin_links_the_season_of_its_first_episode(self, jellyfin_api, library):
        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 5})

        assert response.data['season_url'] == f'{PAGE}?id=season-2&serverId=srv'

    def test_an_episode_found_by_number_needs_no_tmdb_lookup(self, jellyfin_api, library, tmdb_episode_ids):
        self.post(jellyfin_api, (1396, 1, 1))

        tmdb_episode_ids.assert_not_called()

    def test_tmdb_is_asked_without_its_response_cache(self, jellyfin_api, library, tmdb_episode_ids):
        self.post(jellyfin_api, (1396, 1, 3))

        tmdb_episode_ids.assert_called_once_with(1396, 1, 3, use_cache=False)

    def test_a_stored_tvdb_id_needs_no_tmdb_lookup(self, jellyfin_api, library, tmdb_episode_ids, stored_episode):
        stored_episode.external_ids['tvdb_id'] = 202
        stored_episode.save()

        response = self.post(jellyfin_api, (1396, 1, 3))

        assert response.data['results'][0]['url'] == f'{PAGE}?id=ep-2-2&serverId=srv'
        tmdb_episode_ids.assert_not_called()

    def test_a_fetched_tvdb_id_is_stored_for_the_next_lookup(self, jellyfin_api, library, tmdb_episode_ids, stored_episode):
        self.post(jellyfin_api, (1396, 1, 3))
        self.post(jellyfin_api, (1396, 1, 3))

        stored_episode.refresh_from_db()
        assert stored_episode.external_ids == {'tvmaze_id': 9, 'tvdb_id': 201}
        assert tmdb_episode_ids.call_count == 1

    def test_an_episode_without_a_tvdb_id_has_no_link_and_stores_nothing(self, jellyfin_api, library, stored_episode):
        episode = Episode.objects.create(season=stored_episode.season, episode_number=9, tmdb_id=9, name='E9')

        response = self.post(jellyfin_api, (1396, 1, 9))

        assert response.data['results'][0]['url'] is None
        episode.refresh_from_db()
        assert episode.external_ids == {}

    def test_a_tvdb_id_that_jellyfin_lacks_has_no_link(self, jellyfin_api, library, stored_episode):
        stored_episode.external_ids['tvdb_id'] = 999
        stored_episode.save()

        response = self.post(jellyfin_api, (1396, 1, 3))

        assert response.data['results'][0]['url'] is None

    def test_a_tmdb_failure_only_loses_the_unmatched_links(self, jellyfin_api, library, tmdb_episode_ids):
        tmdb_episode_ids.side_effect = requests.ConnectionError('offline')

        response = self.post(jellyfin_api, (1396, 1, 1), (1396, 1, 3))

        assert [result['url'] for result in response.data['results']] == [f'{PAGE}?id=ep-1-1&serverId=srv', None]


class TestUpstreamFailures:
    def test_show_links_degrade_to_no_links_when_jellyfin_is_unreachable(self, jellyfin_api, mocker):
        mocker.patch('requests.Session.request', side_effect=requests.ConnectionError('refused'))

        response = jellyfin_api.get(SHOW_LINKS_URL, {'season': 1, 'episode': 1})

        assert response.status_code == 200
        assert response.data == NO_LINKS

    def test_episode_links_degrade_to_no_links_when_jellyfin_rejects_the_key(self, jellyfin_api, fake_arr):
        fake_arr.on('GET', '/Items', {'error': 'Unauthorized'}, status_code=401)

        response = jellyfin_api.post(
            EPISODE_LINKS_URL, {'items': [{'tmdb_id': 1396, 'season_number': 1, 'episode_number': 1}]}, format='json',
        )

        assert response.status_code == 200
        assert response.data['results'][0]['url'] is None

    def test_failures_are_not_cached(self, jellyfin_api, fake_arr):
        fake_arr.on('GET', '/Items', None, status_code=500)
        assert jellyfin_api.get(SHOW_LINKS_URL).data == NO_LINKS

        fake_arr.on('GET', '/Items', SERIES)

        assert jellyfin_api.get(SHOW_LINKS_URL).data['show_url'] == f'{PAGE}?id=series-bb&serverId=srv'

    def test_a_series_that_fails_only_loses_its_own_links(self, jellyfin_api, library):
        library.on('GET', '/Shows/series-other/Episodes', None, status_code=500)

        response = jellyfin_api.post(
            EPISODE_LINKS_URL,
            {'items': [
                {'tmdb_id': 1396, 'season_number': 1, 'episode_number': 1},
                {'tmdb_id': 1399, 'season_number': 1, 'episode_number': 1},
            ]},
            format='json',
        )

        assert [result['url'] for result in response.data['results']] == [f'{PAGE}?id=ep-1-1&serverId=srv', None]


class TestConnectionPool:
    def test_the_pool_fits_every_parallel_lookup(self, jellyfin_settings):
        adapter = jellyfin_client()._session.get_adapter('https://jellyfin.test')

        assert adapter._pool_maxsize >= MAX_WORKERS


class TestSslVerification:
    def test_verifies_certificates_by_default(self, jellyfin_api, library):
        jellyfin_api.get(SHOW_LINKS_URL)

        assert library.calls[0]['verify'] is True

    def test_verification_can_be_disabled_for_self_signed_certificates(self, jellyfin_api, jellyfin_settings, library):
        jellyfin_settings.JELLYFIN_VERIFY_SSL = False

        jellyfin_api.get(SHOW_LINKS_URL)

        assert library.calls[0]['verify'] is False
