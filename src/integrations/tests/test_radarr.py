import pytest
from django.urls import reverse

MOVIE_URL = reverse('radarr_movie', args=[603])

LOOKUP = {'id': 0, 'title': 'The Matrix', 'tmdbId': 603, 'year': 1999, 'titleSlug': '603', 'images': []}
ADD_PAYLOAD = {
    'quality_profile_id': 4,
    'root_folder_path': '/movies',
    'minimum_availability': 'released',
    'monitored': True,
    'search_for_movie': False,
    'tags': [2],
}

REMOVE_PAYLOAD = {'delete_files': True, 'add_import_exclusion': False}


class TestMovieState:
    def test_reports_movie_not_added(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])

        response = arr_client.get(MOVIE_URL)

        assert response.status_code == 200
        assert response.data == {'added': False}
        assert fake_arr.calls[0]['params'] == {'tmdbId': 603}

    def test_reports_existing_movie(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{
            'id': 9, 'tmdbId': 603, 'titleSlug': 'the-matrix-603', 'path': '/movies/The Matrix (1999)', 'monitored': False,
        }])

        response = arr_client.get(MOVIE_URL)

        assert response.data == {
            'added': True,
            'path': '/movies/The Matrix (1999)',
            'monitored': False,
            'url': 'http://radarr.test:7878/movie/the-matrix-603',
        }

    def test_link_uses_the_public_url_when_set(self, arr_client, arr_settings, fake_arr):
        arr_settings.RADARR_PUBLIC_URL = 'https://radarr.example.com/base'
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'titleSlug': 'the-matrix-603', 'path': '/m', 'monitored': True}])

        response = arr_client.get(MOVIE_URL)

        assert response.data['url'] == 'https://radarr.example.com/base/movie/the-matrix-603'
        assert fake_arr.calls[0]['host'] == 'radarr.test:7878'

    def test_link_falls_back_to_the_tmdb_id_without_a_slug(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])

        response = arr_client.get(MOVIE_URL)

        assert response.data['url'] == 'http://radarr.test:7878/movie/603'

    def test_server_error_returns_502(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', None, status_code=500)

        response = arr_client.get(MOVIE_URL)

        assert response.status_code == 502
        assert 'HTTP 500' in response.data['detail']


class TestAddMovie:
    def test_adds_movie_using_lookup_payload(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])
        fake_arr.on('GET', '/movie/lookup/tmdb', LOOKUP)
        fake_arr.on('POST', '/movie', {
            'id': 9, 'titleSlug': 'the-matrix-603', 'path': '/movies/The Matrix (1999)', 'monitored': True,
        })

        response = arr_client.post(MOVIE_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 201
        assert response.data == {
            'added': True,
            'path': '/movies/The Matrix (1999)',
            'monitored': True,
            'url': 'http://radarr.test:7878/movie/the-matrix-603',
        }
        sent = fake_arr.calls_to('POST', '/movie')[0]['json']
        assert sent['title'] == 'The Matrix'
        assert sent['tmdbId'] == 603
        assert 'id' not in sent
        assert sent['qualityProfileId'] == 4
        assert sent['rootFolderPath'] == '/movies'
        assert sent['minimumAvailability'] == 'released'
        assert sent['monitored'] is True
        assert sent['tags'] == [2]
        assert sent['addOptions'] == {'searchForMovie': False}

    def test_returns_409_when_movie_already_added(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'path': '/movies/The Matrix (1999)', 'monitored': True}])

        response = arr_client.post(MOVIE_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 409
        assert response.data['added'] is True
        assert not fake_arr.calls_to('POST', '/movie')

    def test_returns_404_when_radarr_lookup_finds_nothing(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])
        fake_arr.on('GET', '/movie/lookup/tmdb', [])

        response = arr_client.post(MOVIE_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 404
        assert response.data['detail'] == 'Movie not found in Radarr.'

    @pytest.mark.parametrize(
        'override',
        [
            {'quality_profile_id': 0},
            {'root_folder_path': ''},
            {'minimum_availability': 'tba'},
            {'monitored': None},
            {'tags': ['kids']},
        ],
    )
    def test_rejects_invalid_payload(self, arr_client, fake_arr, override):
        fake_arr.on('GET', '/movie', [])

        response = arr_client.post(MOVIE_URL, {**ADD_PAYLOAD, **override}, format='json')

        assert response.status_code == 400
        assert not fake_arr.calls_to('POST', '/movie')

    def test_requires_explicit_choices(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])

        response = arr_client.post(MOVIE_URL, {}, format='json')

        assert response.status_code == 400
        assert set(response.data) == {
            'quality_profile_id', 'root_folder_path', 'minimum_availability', 'monitored', 'search_for_movie',
        }

    def test_passes_radarr_validation_message_through(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])
        fake_arr.on('GET', '/movie/lookup/tmdb', LOOKUP)
        fake_arr.on(
            'POST', '/movie',
            [{'propertyName': 'RootFolderPath', 'errorMessage': 'Folder is not writable'}],
            status_code=400,
        )

        response = arr_client.post(MOVIE_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 400
        assert response.data['detail'] == 'Folder is not writable'


class TestRemoveMovie:
    def test_removes_movie_with_the_chosen_options(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])
        fake_arr.on('DELETE', '/movie/9', None)

        response = arr_client.delete(MOVIE_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 200
        assert response.data == {'added': False}
        call = fake_arr.calls_to('DELETE', '/movie/9')[0]
        assert call['params'] == {'deleteFiles': 'true', 'addImportExclusion': 'false'}

    def test_returns_404_when_movie_is_not_in_radarr(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [])

        response = arr_client.delete(MOVIE_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 404
        assert response.data['detail'] == 'Movie is not in Radarr.'
        assert not fake_arr.calls_to('DELETE', '/movie/9')

    def test_requires_explicit_options(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])

        response = arr_client.delete(MOVIE_URL, {}, format='json')

        assert response.status_code == 400
        assert set(response.data) == {'delete_files', 'add_import_exclusion'}
        assert not fake_arr.calls_to('DELETE', '/movie/9')

    def test_passes_radarr_error_through(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])
        fake_arr.on('DELETE', '/movie/9', {'message': 'Movie is locked'}, status_code=400)

        response = arr_client.delete(MOVIE_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 400
        assert response.data['detail'] == 'Movie is locked'
