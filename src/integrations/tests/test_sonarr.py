import pytest
import requests
from django.urls import reverse

from media.tests.factories import TVShowFactory

SHOW_URL = reverse('sonarr_series', args=[1396])
TVDB_ID = 81189

LOOKUP_RESULTS = [
    {'id': 0, 'title': 'Other Show', 'tvdbId': 1, 'titleSlug': 'other-show'},
    {'id': 0, 'title': 'Breaking Bad', 'tvdbId': TVDB_ID, 'titleSlug': 'breaking-bad', 'seasons': []},
]
ADD_PAYLOAD = {
    'quality_profile_id': 4,
    'root_folder_path': '/tv',
    'series_type': 'standard',
    'monitor': 'firstSeason',
    'monitored': True,
    'season_folder': True,
    'search_for_missing_episodes': False,
    'tags': [2],
}
REMOVE_PAYLOAD = {'delete_files': True, 'add_import_exclusion': False}
EXISTING = {'id': 9, 'tvdbId': TVDB_ID, 'titleSlug': 'breaking-bad', 'path': '/tv/Breaking Bad', 'monitored': True}


@pytest.fixture
def show_with_tvdb_id(db):
    return TVShowFactory(tmdb_id=1396, external_ids={'tvdb_id': TVDB_ID})


class TestShowState:
    def test_reports_show_not_added_looking_it_up_by_tvdb_id(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])

        response = arr_client.get(SHOW_URL)

        assert response.status_code == 200
        assert response.data == {'added': False}
        assert fake_arr.calls[0]['params'] == {'tvdbId': TVDB_ID}

    def test_reports_existing_show_with_a_link_to_it(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [EXISTING])

        response = arr_client.get(SHOW_URL)

        assert response.data == {
            'added': True,
            'path': '/tv/Breaking Bad',
            'monitored': True,
            'url': 'http://sonarr.test:8989/series/breaking-bad',
        }

    def test_link_uses_the_public_url_when_set(self, arr_client, arr_settings, fake_arr, show_with_tvdb_id):
        arr_settings.SONARR_PUBLIC_URL = 'https://sonarr.example.com/base'
        fake_arr.on('GET', '/series', [EXISTING])

        response = arr_client.get(SHOW_URL)

        assert response.data['url'] == 'https://sonarr.example.com/base/series/breaking-bad'
        assert fake_arr.calls[0]['host'] == 'sonarr.test:8989'


class TestTvdbIdResolution:
    def test_falls_back_to_tmdb_when_the_show_has_no_stored_tvdb_id(self, arr_client, fake_arr, mocker, db):
        TVShowFactory(tmdb_id=1396, external_ids={})
        details = mocker.patch(
            'integrations.media_ids.tmdb.get_tv_details', return_value={'external_ids': {'tvdb_id': TVDB_ID}},
        )
        fake_arr.on('GET', '/series', [])

        response = arr_client.get(SHOW_URL)

        assert response.status_code == 200
        details.assert_called_once_with(1396)
        assert fake_arr.calls[0]['params'] == {'tvdbId': TVDB_ID}

    def test_uses_tmdb_for_shows_that_are_not_stored_locally(self, arr_client, fake_arr, mocker, db):
        mocker.patch('integrations.media_ids.tmdb.get_tv_details', return_value={'external_ids': {'tvdb_id': TVDB_ID}})
        fake_arr.on('GET', '/series', [])

        assert arr_client.get(SHOW_URL).status_code == 200

    def test_returns_422_when_the_show_has_no_tvdb_id(self, arr_client, fake_arr, mocker, db):
        mocker.patch('integrations.media_ids.tmdb.get_tv_details', return_value={'external_ids': {'tvdb_id': None}})

        response = arr_client.get(SHOW_URL)

        assert response.status_code == 422
        assert 'TheTVDB id' in response.data['detail']
        assert not fake_arr.calls

    def test_returns_502_when_tmdb_cannot_be_reached(self, arr_client, mocker, db):
        mocker.patch('integrations.media_ids.tmdb.get_tv_details', side_effect=requests.ConnectionError('down'))

        response = arr_client.get(SHOW_URL)

        assert response.status_code == 502


class TestAddShow:
    def test_adds_show_using_the_matching_lookup_result(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])
        fake_arr.on('GET', '/series/lookup', LOOKUP_RESULTS)
        fake_arr.on('POST', '/series', {**EXISTING})

        response = arr_client.post(SHOW_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 201
        assert response.data['url'] == 'http://sonarr.test:8989/series/breaking-bad'
        assert fake_arr.calls_to('GET', '/series/lookup')[0]['params'] == {'term': f'tvdb:{TVDB_ID}'}
        sent = fake_arr.calls_to('POST', '/series')[0]['json']
        assert sent['title'] == 'Breaking Bad'
        assert sent['tvdbId'] == TVDB_ID
        assert 'id' not in sent
        assert sent['qualityProfileId'] == 4
        assert sent['rootFolderPath'] == '/tv'
        assert sent['seriesType'] == 'standard'
        assert sent['seasonFolder'] is True
        assert sent['monitored'] is True
        assert sent['tags'] == [2]
        assert sent['addOptions'] == {'monitor': 'firstSeason', 'searchForMissingEpisodes': False}

    def test_returns_409_when_show_already_added(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [EXISTING])

        response = arr_client.post(SHOW_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 409
        assert response.data['added'] is True
        assert not fake_arr.calls_to('POST', '/series')

    def test_returns_404_when_lookup_has_no_matching_result(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])
        fake_arr.on('GET', '/series/lookup', [LOOKUP_RESULTS[0]])

        response = arr_client.post(SHOW_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 404
        assert response.data['detail'] == 'Series not found in Sonarr.'

    @pytest.mark.parametrize(
        'override',
        [
            {'quality_profile_id': 0},
            {'root_folder_path': ''},
            {'series_type': 'miniseries'},
            {'monitor': 'everything'},
            {'season_folder': None},
            {'tags': ['kids']},
        ],
    )
    def test_rejects_invalid_payload(self, arr_client, fake_arr, show_with_tvdb_id, override):
        fake_arr.on('GET', '/series', [])

        response = arr_client.post(SHOW_URL, {**ADD_PAYLOAD, **override}, format='json')

        assert response.status_code == 400
        assert not fake_arr.calls_to('POST', '/series')

    def test_requires_explicit_choices(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])

        response = arr_client.post(SHOW_URL, {}, format='json')

        assert response.status_code == 400
        assert set(response.data) == {
            'quality_profile_id', 'root_folder_path', 'monitored', 'series_type', 'monitor',
            'season_folder', 'search_for_missing_episodes',
        }

    def test_passes_sonarr_validation_message_through(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])
        fake_arr.on('GET', '/series/lookup', LOOKUP_RESULTS)
        fake_arr.on(
            'POST', '/series',
            [{'propertyName': 'RootFolderPath', 'errorMessage': 'Folder is not writable'}],
            status_code=400,
        )

        response = arr_client.post(SHOW_URL, ADD_PAYLOAD, format='json')

        assert response.status_code == 400
        assert response.data['detail'] == 'Folder is not writable'


class TestRemoveShow:
    def test_removes_show_with_the_sonarr_exclusion_parameter(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [EXISTING])
        fake_arr.on('DELETE', '/series/9', None)

        response = arr_client.delete(SHOW_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 200
        assert response.data == {'added': False}
        call = fake_arr.calls_to('DELETE', '/series/9')[0]
        assert call['params'] == {'deleteFiles': 'true', 'addImportListExclusion': 'false'}

    def test_returns_404_when_show_is_not_in_sonarr(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [])

        response = arr_client.delete(SHOW_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 404
        assert response.data['detail'] == 'Series is not in Sonarr.'

    def test_requires_explicit_options(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [EXISTING])

        response = arr_client.delete(SHOW_URL, {}, format='json')

        assert response.status_code == 400
        assert not fake_arr.calls_to('DELETE', '/series/9')

    def test_passes_sonarr_error_through(self, arr_client, fake_arr, show_with_tvdb_id):
        fake_arr.on('GET', '/series', [EXISTING])
        fake_arr.on('DELETE', '/series/9', {'message': 'Series is locked'}, status_code=400)

        response = arr_client.delete(SHOW_URL, REMOVE_PAYLOAD, format='json')

        assert response.status_code == 400
        assert response.data['detail'] == 'Series is locked'
