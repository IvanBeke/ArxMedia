import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from tracking.models import DataTransferJob
from tracking.tasks import prepare_import_job

pytestmark = pytest.mark.django_db

CSV_HEADER = 'source,media_type,media_id,season_number,episode_number,status,score,progress,start_date,end_date,progressed_at,created_at,notes'


def _yamtrack_upload():
    rows = [
        CSV_HEADER,
        'tmdb,movie,100,,,Completed,8,,,,,,',
        'mal,anime,999,,,Completed,,,,,,,',
    ]
    return SimpleUploadedFile('yamtrack.csv', ('\n'.join(rows) + '\n').encode(), content_type='text/csv')


def _prepare_job(user):
    client = APIClient()
    assert client.login(username=user.username, password='testpass123')
    response = client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': _yamtrack_upload()}, format='multipart')
    assert response.status_code == 201
    prepare_import_job(response.data['id'])
    return DataTransferJob.objects.get(id=response.data['id'])


def _warning_messages(job):
    report = job.metadata.get('report') or job.metadata
    return [warning['message'] for warning in report.get('warnings', [])]


class TestImportMessagesFollowTheJobOwnerLanguage:
    def test_stored_warnings_are_written_in_english_by_default(self, user, tmdb_noop):
        job = _prepare_job(user)

        assert 'Only rows with source tmdb can be imported.' in _warning_messages(job)

    def test_stored_warnings_are_written_in_the_owner_language(self, user, tmdb_noop):
        user.language = 'es'
        user.save(update_fields=['language'])

        job = _prepare_job(user)

        assert 'Solo se pueden importar las filas con origen tmdb.' in _warning_messages(job)

    def test_validation_errors_follow_the_requesting_user_language(self, user):
        user.language = 'es'
        user.save(update_fields=['language'])
        client = APIClient()
        assert client.login(username=user.username, password='testpass123')

        response = client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {}, format='multipart')

        assert response.status_code == 400
        assert 'file es obligatorio' in str(response.json())
