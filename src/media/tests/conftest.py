"""Shared fixtures for media tests: fake TMDB GET responses."""

import pytest

_EMPTY_LIST = {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

_MOVIE_550 = {
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

_TV_1399 = {
    'id': 1399,
    'name': 'Game of Thrones',
    'overview': 'Mocked show',
    'first_air_date': '2011-04-17',
    'number_of_seasons': 1,
    'number_of_episodes': 1,
    'episode_run_time': [57],
    'genres': [],
    'networks': [],
}

_SEASON_1 = {
    'id': 139901,
    'season_number': 1,
    'name': 'Season 1',
    'episode_count': 1,
    'episodes': [
        {
            'id': 13990101,
            'episode_number': 1,
            'name': 'Winter Is Coming',
            'air_date': '2011-04-17',
            'episode_type': 'finale',
        }
    ],
}

_MOCK_ENDPOINTS = {
    '/movie/550': _MOVIE_550,
    '/movie/550/watch/providers': {'results': {}},
    '/tv/1399': _TV_1399,
    '/tv/1399/watch/providers': {'results': {}},
    '/tv/1399/season/1': _SEASON_1,
    '/tv/1399/season/1/episode/1/credits': {'cast': [], 'crew': []},
}

_LIST_ENDPOINTS = ('/movie/popular', '/tv/popular', '/search/multi')


def fake_tmdb_get(endpoint, params=None, **kwargs):
    payload = _MOCK_ENDPOINTS.get(endpoint)
    if payload is not None:
        return payload
    if endpoint in _LIST_ENDPOINTS or endpoint.startswith('/trending/'):
        return _EMPTY_LIST
    return {}


@pytest.fixture(autouse=True)
def _tmdb_fake_get(request, mocker):
    """Fake TMDBService._get for every media test; per-test patches nest over it.

    Tests that exercise _get itself opt out with @pytest.mark.unfaked_tmdb_get
    (their HTTP layer is still mocked — see _block_real_http in src/conftest.py).
    """
    if request.node.get_closest_marker("unfaked_tmdb_get"):
        yield None
        return
    yield mocker.patch('media.tmdb.TMDBService._get', side_effect=fake_tmdb_get)
