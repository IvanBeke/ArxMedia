"""Shared fixtures for media tests: fake TMDB GET responses."""

import pytest


def fake_tmdb_get(endpoint, params=None, **kwargs):
    if endpoint == '/movie/popular':
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
    if endpoint == '/tv/popular':
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
    if endpoint == '/search/multi':
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
    if endpoint.startswith('/trending/'):
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

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
    if endpoint == '/movie/550/watch/providers':
        return {'results': {}}

    if endpoint == '/tv/1399':
        return {
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
    if endpoint == '/tv/1399/watch/providers':
        return {'results': {}}
    if endpoint == '/tv/1399/season/1':
        return {
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
    if endpoint == '/tv/1399/season/1/episode/1/credits':
        return {'cast': [], 'crew': []}

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
