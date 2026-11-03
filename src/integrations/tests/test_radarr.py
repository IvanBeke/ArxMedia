import pytest
import requests
from django.urls import reverse

OPTIONS_URL = reverse('radarr_options')
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


@pytest.fixture
def radarr_options_routes(fake_arr):
    fake_arr.on('GET', '/rootfolder', [{'id': 1, 'path': '/movies', 'freeSpace': 1000, 'accessible': True}])
    fake_arr.on('GET', '/qualityprofile', [{'id': 4, 'name': 'HD-1080p', 'cutoff': 7}])
    fake_arr.on('GET', '/tag', [{'id': 2, 'label': 'kids'}])
    return fake_arr


class TestPermissionGate:
    @pytest.mark.parametrize('url', [OPTIONS_URL, MOVIE_URL])
    def test_anonymous_gets_401(self, api_client, arr_settings, url):
        assert api_client.get(url).status_code == 401

    @pytest.mark.parametrize('url', [OPTIONS_URL, MOVIE_URL])
    def test_user_without_permission_gets_403(self, auth_client, arr_settings, url):
        assert auth_client.get(url).status_code == 403

    def test_post_without_permission_gets_403(self, auth_client, arr_settings):
        assert auth_client.post(MOVIE_URL, ADD_PAYLOAD, format='json').status_code == 403

    def test_superuser_is_allowed(self, api_client, user, arr_settings, radarr_options_routes):
        user.is_superuser = True
        user.save()
        api_client.force_authenticate(user=user)

        assert api_client.get(OPTIONS_URL).status_code == 200


class TestUnconfigured:
    @pytest.mark.parametrize('url', [OPTIONS_URL, MOVIE_URL])
    def test_returns_503_when_radarr_is_not_configured(self, api_client, arr_user, settings, url):
        settings.RADARR_URL = ''
        settings.RADARR_API_KEY = ''
        api_client.force_authenticate(user=arr_user)

        response = api_client.get(url)

        assert response.status_code == 503
        assert response.data['detail'] == 'Radarr is not configured.'


class TestOptions:
    def test_returns_normalized_options(self, arr_client, radarr_options_routes):
        response = arr_client.get(OPTIONS_URL)

        assert response.status_code == 200
        assert response.data == {
            'root_folders': [{'path': '/movies', 'free_space': 1000}],
            'quality_profiles': [{'id': 4, 'name': 'HD-1080p'}],
            'tags': [{'id': 2, 'label': 'kids'}],
        }
        assert radarr_options_routes.calls[0]['headers']['X-Api-Key'] == 'radarr-key'
        assert radarr_options_routes.calls[0]['url'].startswith('http://radarr.test:7878/api/v3/')


class TestSslVerification:
    def test_verifies_certificates_by_default(self, arr_client, radarr_options_routes):
        arr_client.get(OPTIONS_URL)

        assert radarr_options_routes.calls[0]['verify'] is True

    def test_verification_can_be_disabled_for_self_signed_certificates(self, arr_client, arr_settings, radarr_options_routes):
        arr_settings.RADARR_VERIFY_SSL = False

        arr_client.get(OPTIONS_URL)

        assert radarr_options_routes.calls[0]['verify'] is False


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
        assert fake_arr.calls[0]['url'].startswith('http://radarr.test:7878/')

    def test_link_falls_back_to_the_tmdb_id_without_a_slug(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])

        response = arr_client.get(MOVIE_URL)

        assert response.data['url'] == 'http://radarr.test:7878/movie/603'


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
        assert not fake_arr.calls_to('DELETE', '/movie/9')

    def test_requires_explicit_options(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])

        response = arr_client.delete(MOVIE_URL, {}, format='json')

        assert response.status_code == 400
        assert set(response.data) == {'delete_files', 'add_import_exclusion'}
        assert not fake_arr.calls_to('DELETE', '/movie/9')

    def test_requires_permission(self, auth_client, arr_settings):
        assert auth_client.delete(MOVIE_URL, REMOVE_PAYLOAD, format='json').status_code == 403

    def test_passes_radarr_error_through(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', [{'id': 9, 'tmdbId': 603, 'path': '/m', 'monitored': True}])
        fake_arr.on('DELETE', '/movie/9', {'message': 'Movie is locked'}, status_code=400)

        response = arr_client.delete(MOVIE_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 400
        assert response.data['detail'] == 'Movie is locked'


class TestUpstreamFailures:
    def test_unreachable_radarr_returns_502(self, arr_client, mocker):
        mocker.patch('requests.Session.request', side_effect=requests.ConnectionError('refused'))

        response = arr_client.get(OPTIONS_URL)

        assert response.status_code == 502
        assert response.data['detail'] == 'Could not reach Radarr.'

    def test_rejected_api_key_returns_502(self, arr_client, fake_arr):
        fake_arr.on('GET', '/rootfolder', {'error': 'Unauthorized'}, status_code=401)

        response = arr_client.get(OPTIONS_URL)

        assert response.status_code == 502
        assert response.data['detail'] == 'Radarr rejected the API key.'

    def test_server_error_returns_502(self, arr_client, fake_arr):
        fake_arr.on('GET', '/movie', None, status_code=500)

        response = arr_client.get(MOVIE_URL)

        assert response.status_code == 502
        assert 'HTTP 500' in response.data['detail']
