import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class DataImportExportTests(BaseTestCase):
    def test_export_contains_json_file_per_key_and_lists_without_collaborators(self):
        from tracking.tasks.export import export_user_data

        planned_at = datetime(2025, 4, 5, 12, 30, tzinfo=UTC)
        UserMediaStatus.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=9101,
            status='plan_to_watch',
            plan_to_watch_at=planned_at,
            status_changed_at=planned_at,
        )
        custom_list = CustomList.objects.create(
            user=self.user,
            name='Exported List',
            description='A backup list',
            privacy='private',
        )
        ListItem.objects.create(custom_list=custom_list, media_type='movie', tmdb_id=9102, custom_order=3)
        ListCollaborator.objects.create(custom_list=custom_list, user=self.user2)
        job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip')

        export_user_data.run(job.id)

        job.refresh_from_db()
        self.assertTrue(job.output_file.name.endswith('.zip'))
        self.assertRegex(
            job.output_file.name,
            r'^exports/[0-9a-f]{32}/arxmedia_export_testuser_\d{4}(_\d{2}){4}(_\w+)?\.zip$',
        )
        with job.output_file.open('rb') as export_file, zipfile.ZipFile(export_file) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {'watch_history.json', 'watchlist.json', 'ratings.json', 'dropped.json', 'lists.json'},
            )
            payload = {
                file_name.removesuffix('.json'): json.loads(archive.read(file_name))
                for file_name in archive.namelist()
            }
        self.assertEqual(payload['watch_history'], [])
        self.assertEqual(payload['watchlist'], [
            {'media_type': 'movie', 'tmdb_id': 9101, 'plan_to_watch_at': planned_at.isoformat()},
        ])
        self.assertEqual(payload['dropped'], [])
        self.assertEqual(payload['ratings'], [])
        self.assertEqual(payload['lists'][0]['name'], 'Exported List')
        self.assertNotIn('collaborators', payload['lists'][0])
        self.assertEqual(payload['lists'][0]['items'][0]['custom_order'], 3)

        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        with job.output_file.open('rb') as export_file:
            parsed = parse_arxmedia_zip(export_file.read())
        self.assertEqual(parsed.report['summary']['lists'], 1)
        self.assertEqual(parsed.lists[0].items[0].tmdb_id, 9102)

    def test_arxmedia_zip_import_reads_each_json_key(self):
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watch_history.json', json.dumps([
                {'media_type': 'movie', 'tmdb_id': 9250, 'watched_at': '2025-01-02T03:04:05Z'},
            ]))
            archive.writestr('watchlist.json', json.dumps([
                {'media_type': 'tv', 'tmdb_id': 9251},
            ]))
            archive.writestr('ratings.json', json.dumps([
                {'media_type': 'movie', 'tmdb_id': 9252, 'score': 8, 'created_at': '2025-01-03T03:04:05Z', 'updated_at': '2025-01-03T03:04:05Z'},
            ]))
            archive.writestr('dropped.json', json.dumps([
                {'media_type': 'tv', 'tmdb_id': 9254, 'dropped_at': '2025-01-04T03:04:05Z'},
            ]))
            archive.writestr('lists.json', json.dumps([
                {'name': 'Zipped List', 'items': [{'media_type': 'tv', 'tmdb_id': 9253}]},
            ]))

        parsed = parse_arxmedia_zip(buffer.getvalue())

        self.assertEqual(parsed.report['format'], 'zip')
        self.assertEqual(parsed.report['files_processed'], 5)
        self.assertEqual(parsed.report['summary'], {
            'watch_history': 1,
            'watchlist': 1,
            'ratings': 1,
            'dropped': 1,
            'lists': 1,
        })
        self.assertEqual(parsed.watch_entries()[0].tmdb_id, 9250)
        self.assertEqual(parsed.statuses()[0].tmdb_id, 9251)
        self.assertEqual(parsed.ratings()[0].tmdb_id, 9252)
        dropped = next(record for record in parsed.statuses() if record.status == 'dropped')
        self.assertEqual(dropped.tmdb_id, 9254)
        self.assertEqual(dropped.status_at.isoformat(), '2025-01-04T03:04:05+00:00')
        self.assertEqual(parsed.lists[0].name, 'Zipped List')

    def test_arxmedia_zip_reports_a_bad_collection_without_discarding_others(self):
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watch_history.json', json.dumps([
                {'media_type': 'movie', 'tmdb_id': 9260},
            ]))
            archive.writestr('ratings.json', '{invalid json')

        parsed = parse_arxmedia_zip(buffer.getvalue())

        self.assertEqual(parsed.report['files_failed'], 1)
        self.assertEqual(parsed.report['summary']['watch_history'], 1)
        self.assertEqual(parsed.report['summary']['ratings'], 0)
        self.assertIn('file_parse_error', {warning['code'] for warning in parsed.report['warnings']})

    def test_arxmedia_import_preserves_plan_date_and_restores_lists(self):
        from tracking.import_engine import apply_imported_lists
        from tracking.import_records import LISTS_COLLECTION
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        planned_at = datetime(2024, 8, 9, 10, 15, tzinfo=UTC)
        added_at = datetime(2024, 8, 10, 10, 15, tzinfo=UTC)
        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({
            'watchlist': [{
                'media_type': 'movie',
                'tmdb_id': 9201,
                'plan_to_watch_at': planned_at.isoformat(),
            }],
            'lists': [{
                'name': 'Imported List',
                'description': 'Imported description',
                'privacy': 'private',
                'items': [{
                    'media_type': 'tv',
                    'tmdb_id': 9202,
                    'added_at': added_at.isoformat(),
                    'custom_order': 4,
                }],
            }],
        }))

        status = parsed.statuses()[0]
        self.assertEqual(status.status_at, planned_at)
        self.assertIn(LISTS_COLLECTION, parsed.collections_present)
        self.assertEqual(apply_imported_lists(self.user, parsed, 'new_items'), {
            'lists_created': 1, 'lists_updated': 0,
            'items_created': 1, 'items_updated': 0, 'items_deleted': 0,
        })
        imported_status = UserMediaStatus.objects.create(
            user=self.user,
            media_type=status.media_type,
            tmdb_id=status.tmdb_id,
            status=status.status,
            plan_to_watch_at=status.status_at,
            status_changed_at=status.status_at,
        )
        self.assertEqual(imported_status.plan_to_watch_at, planned_at)
        imported_list = CustomList.objects.get(user=self.user, name='Imported List')
        imported_item = ListItem.objects.get(custom_list=imported_list)
        self.assertEqual(imported_item.custom_order, 4)
        self.assertEqual(imported_item.added_at, added_at)
        self.assertFalse(ListCollaborator.objects.filter(custom_list=imported_list).exists())

    def test_arxmedia_export_import_round_trips_dropped_status(self):
        from tracking.tasks.export import export_user_data
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        dropped_at = datetime(2024, 5, 6, 7, 8, tzinfo=UTC)
        UserMediaStatus.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=9205,
            status='dropped',
            dropped_at=dropped_at,
            status_changed_at=dropped_at,
        )
        job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip')
        export_user_data.run(job.id)

        job.refresh_from_db()
        with job.output_file.open('rb') as export_file:
            parsed = parse_arxmedia_zip(export_file.read())

        status = parsed.statuses()[0]
        self.assertEqual(status.status, 'dropped')
        self.assertEqual(status.tmdb_id, 9205)
        self.assertEqual(status.status_at, dropped_at)

    def test_imported_rating_preserves_source_rated_at(self):
        from tracking.import_engine import apply_item_records, group_by_item
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        rated_at = datetime(2025, 1, 6, 3, 4, 5, tzinfo=UTC)
        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({
            'ratings': [{
                'media_type': 'movie',
                'tmdb_id': 9206,
                'score': 9,
                'created_at': rated_at.isoformat(),
                'updated_at': rated_at.isoformat(),
            }],
        }))

        item = next(item for item in group_by_item(parsed) if item['tmdb_id'] == 9206)
        apply_item_records(self.user, item['media_type'], item['tmdb_id'], item['records'], 'new_items')

        rating = Rating.objects.get(user=self.user, media_type='movie', tmdb_id=9206)
        self.assertEqual(rating.score, 9)
        self.assertEqual(rating.created_at, rated_at)
        self.assertEqual(rating.updated_at, rated_at)

    def test_export_file_delete_is_scoped_to_owner(self):
        import os

        from django.core.files.base import ContentFile

        job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip', status='done')
        job.output_file.save('arxmedia_export_testuser_2026_09_25_23_05.zip', ContentFile(b'zip-bytes'), save=True)
        stored_path = job.output_file.path
        self.assertTrue(os.path.exists(stored_path))

        self.authenticate(self.user2)
        response = self.client.delete(f'/api/tracking/data/jobs/{job.id}/file/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('error_code'), 'IMPORT_JOB_NOT_FOUND')
        self.assertTrue(os.path.exists(stored_path))

        self.authenticate(self.user)
        response = self.client.delete(f'/api/tracking/data/jobs/{job.id}/file/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['output_url'])
        job.refresh_from_db()
        self.assertFalse(job.output_file)
        self.assertFalse(os.path.exists(stored_path))

    def test_export_file_download_is_scoped_to_owner(self):
        from django.core.files.base import ContentFile

        job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip', status='done')
        job.output_file.save('arxmedia_export_testuser_2026_09_25_23_05.zip', ContentFile(b'zip-bytes'), save=True)
        self.addCleanup(job.output_file.delete, save=False)

        listed = self.client.get(f'/api/tracking/data/jobs/{job.id}/')
        self.assertTrue(listed.data['output_url'].endswith(f'/api/tracking/data/jobs/{job.id}/file/'))
        self.assertEqual(listed.data['output_filename'], 'arxmedia_export_testuser_2026_09_25_23_05.zip')

        self.assertEqual(self.client.get(f'/media/{job.output_file.name}').status_code, 404)

        self.authenticate(self.user2)
        self.assertEqual(self.client.get(f'/api/tracking/data/jobs/{job.id}/file/').status_code, 400)

        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f'/api/tracking/data/jobs/{job.id}/file/').status_code, 401)

        self.authenticate(self.user)
        response = self.client.get(f'/api/tracking/data/jobs/{job.id}/file/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'zip-bytes')
        self.assertIn('attachment; filename="arxmedia_export_testuser_2026_09_25_23_05.zip"', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_export_file_download_missing_file_returns_404(self):
        job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip', status='done')
        self.assertEqual(self.client.get(f'/api/tracking/data/jobs/{job.id}/file/').status_code, 404)

    def test_export_file_delete_rejects_import_jobs(self):
        job = DataTransferJob.objects.create(user=self.user, job_type='import', data_format='zip', status='done', source='trakt')
        response = self.client.delete(f'/api/tracking/data/jobs/{job.id}/file/')
        self.assertEqual(response.status_code, 400)

    def test_final_report_includes_list_details_with_titles(self):
        from tracking.import_engine import build_final_report
        from tracking.import_records import LISTS_COLLECTION, ListItemRecord, ListRecord, ParsedImport

        Movie.objects.create(tmdb_id=9501, title='Detail Movie')
        parsed = ParsedImport(
            records=(),
            collections_present=frozenset({LISTS_COLLECTION}),
            invalid_count=0,
            report={},
            lists=(
                ListRecord(
                    name='Details',
                    privacy='private',
                    items=(
                        ListItemRecord(media_type='movie', tmdb_id=9501, added_at=timezone.now()),
                        ListItemRecord(media_type='tv', tmdb_id=9502, added_at=timezone.now()),
                    ),
                ),
            ),
        )
        job = DataTransferJob.objects.create(user=self.user, job_type='import', data_format='zip', status='processing')

        report = build_final_report(job, parsed, applied_count=0)

        self.assertEqual(report['list_details'], [{
            'name': 'Details',
            'privacy': 'private',
            'items': [
                {'media_type': 'movie', 'tmdb_id': 9501, 'title': 'Detail Movie'},
                {'media_type': 'tv', 'tmdb_id': 9502, 'title': None},
            ],
        }])

    def test_invalid_only_lists_are_not_mirrorable(self):
        from tracking.import_records import LISTS_COLLECTION
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        CustomList.objects.create(user=self.user, name='Keep Me')
        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({'lists': [{'name': ''}]}))

        self.assertNotIn(LISTS_COLLECTION, parsed.collections_present)
        from tracking.import_engine import delete_missing_rows
        delete_missing_rows(self.user, parsed)
        self.assertTrue(CustomList.objects.filter(user=self.user, name='Keep Me').exists())

    def test_arxmedia_parser_warns_on_invalid_collections_and_list_privacy(self):
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({
            'watch_history': {},
            'lists': [{
                'name': 'Needs normalization',
                'privacy': 'unknown',
                'items': [{'media_type': 'movie', 'tmdb_id': 9401, 'custom_order': -1}],
            }],
        }))

        warning_codes = {warning['code'] for warning in parsed.report['warnings']}
        self.assertIn('invalid_collection', warning_codes)
        self.assertIn('invalid_list_privacy', warning_codes)
        self.assertIn('invalid_list_item', warning_codes)
        self.assertEqual(parsed.lists[0].privacy, 'public')

    def test_arxmedia_parser_rejects_case_insensitive_duplicate_lists(self):
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({'lists': [
            {'name': 'Favorites'},
            {'name': 'favorites'},
        ]}))

        self.assertEqual(len(parsed.lists), 1)
        self.assertIn('duplicate_list', {warning['code'] for warning in parsed.report['warnings']})

    def test_update_existing_import_updates_list_item_order(self):
        from tracking.import_engine import apply_imported_lists
        from tracking.tasks.providers.arxmedia import parse_arxmedia_zip

        custom_list = CustomList.objects.create(user=self.user, name='Ordered List')
        existing = ListItem.objects.create(custom_list=custom_list, media_type='movie', tmdb_id=9301, custom_order=0)
        parsed = parse_arxmedia_zip(self._build_arxmedia_zip({'lists': [{
            'name': 'Ordered List',
            'items': [{'media_type': 'movie', 'tmdb_id': 9301, 'custom_order': 7}],
        }]}))

        self.assertEqual(apply_imported_lists(self.user, parsed, 'update_existing'), {
            'lists_created': 0, 'lists_updated': 1,
            'items_created': 0, 'items_updated': 1, 'items_deleted': 0,
        })
        existing.refresh_from_db()
        self.assertEqual(existing.custom_order, 7)

    def test_mirror_deletion_report_counts_removed_rows(self):
        from tracking.import_engine import delete_missing_rows
        from tracking.import_records import (
            RATINGS_COLLECTION,
            WATCH_HISTORY_COLLECTION,
            WATCHLIST_COLLECTION,
            ParsedImport,
            RatingRecord,
            StatusRecord,
            WatchEntryRecord,
        )

        stale_history = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=9001)
        stale_watchlist = UserMediaStatus.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=9002,
            status='plan_to_watch',
        )
        stale_rating = Rating.objects.create(user=self.user, media_type='movie', tmdb_id=9003, score=7)
        parsed = ParsedImport(
            records=(
                WatchEntryRecord(media_type='movie', tmdb_id=1001),
                StatusRecord(media_type='movie', tmdb_id=1002, status='plan_to_watch'),
                RatingRecord(media_type='movie', tmdb_id=1003, score=8),
            ),
            collections_present=frozenset({WATCH_HISTORY_COLLECTION, WATCHLIST_COLLECTION, RATINGS_COLLECTION}),
            invalid_count=0,
            report={},
        )

        deleted = delete_missing_rows(self.user, parsed)

        self.assertEqual(deleted, {
            WATCH_HISTORY_COLLECTION: 1,
            WATCHLIST_COLLECTION: 1,
            RATINGS_COLLECTION: 1,
        })
        self.assertFalse(WatchEntry.objects.filter(id=stale_history.id).exists())
        self.assertFalse(UserMediaStatus.objects.filter(id=stale_watchlist.id).exists())
        self.assertFalse(Rating.objects.filter(id=stale_rating.id).exists())

    def test_plan_to_watch_import_writes_no_watch_dates(self):
        from tracking.import_engine import _apply_status_winner, _upsert_status
        from tracking.import_records import StatusRecord

        record = StatusRecord(media_type='tv', tmdb_id=6101, status='plan_to_watch')
        _upsert_status(self.user, 'tv', 6101, [record], 'new_items')
        created = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=6101)
        self.assertEqual(created.status, 'plan_to_watch')
        self.assertIsNone(created.started_at)
        self.assertIsNone(created.last_watched_at)

        stale = UserMediaStatus.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=6102,
            status='plan_to_watch',
            started_at=timezone.now(),
            last_watched_at=timezone.now(),
        )
        _apply_status_winner(
            self.user,
            StatusRecord(media_type='tv', tmdb_id=6102, status='plan_to_watch'),
        )
        stale.refresh_from_db()
        self.assertIsNone(stale.started_at)
        self.assertIsNone(stale.last_watched_at)

    def _csv_bytes(self, fieldnames, rows):
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode('utf-8')

    def _build_arxmedia_zip(self, payload=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for collection in ('watch_history', 'watchlist', 'ratings', 'dropped', 'lists'):
                archive.writestr(f'{collection}.json', json.dumps((payload or {}).get(collection, [])))
        return buffer.getvalue()

    def _build_wetrakr_zip(self, tracklog=(), ratings=(), favorites=(), lists=(), prefix=''):
        schemas = {
            'tracklog.csv': (
                [
                    'title', 'year', 'type', 'tmdb_id', 'imdb_id', 'show_title',
                    'season_number', 'episode_number', 'status', 'tracked_at', 'updated_at', 'source',
                ],
                tracklog,
            ),
            'ratings.csv': (
                ['title', 'year', 'type', 'tmdb_id', 'imdb_id', 'show_title', 'season_number', 'episode_number', 'rating', 'rated_at'],
                ratings,
            ),
            'favorites.csv': (['title', 'year', 'type', 'tmdb_id', 'imdb_id', 'created_at'], favorites),
            'lists.csv': (
                ['list_name', 'list_description', 'title', 'year', 'type', 'tmdb_id', 'imdb_id', 'rank', 'created_at'],
                lists,
            ),
            'notes.csv': (
                ['title', 'year', 'type', 'tmdb_id', 'imdb_id', 'show_title', 'season_number', 'episode_number', 'text', 'privacy', 'spoiler', 'created_at'],
                (),
            ),
            'profile.csv': (['username', 'email', 'display_name', 'joined_at', 'plan', 'timezone', 'country'], ()),
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for file_name, (fieldnames, rows) in schemas.items():
                archive.writestr(f'{prefix}{file_name}', self._csv_bytes(fieldnames, rows))
        return buffer.getvalue()

    def _build_yamtrack_csv(self, rows):
        header = [
            'source',
            'media_type',
            'media_id',
            'season_number',
            'episode_number',
            'status',
            'score',
            'progress',
            'start_date',
            'end_date',
            'progressed_at',
            'created_at',
            'notes',
        ]
        lines = [','.join(header)]
        for row in rows:
            values = [str(row.get(key, '')) for key in header]
            lines.append(','.join(values))
        return ('\n'.join(lines) + '\n').encode('utf-8')

    def test_export_job_creation_defaults_to_zip(self):
        response = self.client.post('/api/tracking/data/export/', {})
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['data_format'], 'zip')

    def test_export_rejects_non_zip_format(self):
        response = self.client.post('/api/tracking/data/export/?data_format=json', {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['format'], 'format must be zip')

    def test_import_job_creation(self):
        file_obj = SimpleUploadedFile(
            'arxmedia-export.zip',
            self._build_arxmedia_zip({'watch_history': []}),
            content_type='application/zip',
        )
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['data_format'], 'zip')

    def test_arxmedia_import_rejects_json_format(self):
        file_obj = SimpleUploadedFile('arxmedia-export.json', b'{"watch_history": []}', content_type='application/json')
        response = self.client.post(
            '/api/tracking/data/import/?data_format=json&source=arxmedia',
            {'file': file_obj},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['format'], 'format must be csv or zip')

    def test_import_rejects_oversized_upload(self):
        file_obj = SimpleUploadedFile('big.zip', b'zip-bytes', content_type='application/zip')
        with patch('tracking.views.transfer.MAX_IMPORT_UPLOAD_BYTES', 4):
            response = self.client.post('/api/tracking/data/import/?source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertIn('file', response.data)
        self.assertFalse(DataTransferJob.objects.filter(user=self.user, job_type='import').exists())

    def test_import_archive_rejects_zip_bombs_before_extracting(self):
        from tracking.import_config import open_import_zip
        from tracking.tasks.providers import parse_arxmedia_zip, parse_trakt_zip, parse_wetrakr_zip

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watch_history.json', b'0' * 2048)
        content = buffer.getvalue()

        with patch('tracking.import_config.MAX_IMPORT_ARCHIVE_UNCOMPRESSED_BYTES', 1024):
            for parser in (parse_arxmedia_zip, parse_trakt_zip, parse_wetrakr_zip):
                with self.subTest(parser=parser.__name__), self.assertRaisesMessage(ValueError, 'too large when extracted'):
                    parser(content)
        with patch('tracking.import_config.MAX_IMPORT_ARCHIVE_ENTRIES', 0), self.assertRaisesMessage(ValueError, 'too many files'):
            open_import_zip(content)

    def test_import_and_export_are_rate_limited(self):

        django_cache.clear()
        self.addCleanup(django_cache.clear)
        rates = {**settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'data_import': '1/hour', 'data_export': '1/hour'}
        with patch('rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES', rates):
            for expected in (201, 429):
                file_obj = SimpleUploadedFile('a.zip', self._build_arxmedia_zip(), content_type='application/zip')
                response = self.client.post('/api/tracking/data/import/?source=arxmedia', {'file': file_obj}, format='multipart')
                self.assertEqual(response.status_code, expected)
            self.assertEqual(self.client.post('/api/tracking/data/export/').status_code, 201)
            self.assertEqual(self.client.post('/api/tracking/data/export/').status_code, 429)

    def test_arxmedia_import_defaults_to_zip(self):
        file_obj = SimpleUploadedFile(
            'arxmedia-export.zip',
            self._build_arxmedia_zip(),
            content_type='application/zip',
        )
        response = self.client.post(
            '/api/tracking/data/import/?source=arxmedia',
            {'file': file_obj},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'zip')

    def test_zip_import_job_creation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('lists-watchlist.json', '[]')
        file_obj = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')

        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'zip')

    def test_arxmedia_zip_import_job_creation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watch_history.json', '[]')
        upload = SimpleUploadedFile('arxmedia-export.zip', buffer.getvalue(), content_type='application/zip')

        response = self.client.post(
            '/api/tracking/data/import/?data_format=zip&source=arxmedia',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'zip')
        self.assertEqual(response.data['source'], 'arxmedia')

    def test_wetrakr_zip_import_job_creation(self):
        upload = SimpleUploadedFile(
            'wetrakr_export_user.zip',
            self._build_wetrakr_zip(),
            content_type='application/zip',
        )

        response = self.client.post(
            '/api/tracking/data/import/?data_format=zip&source=wetrakr',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'zip')
        self.assertEqual(response.data['source'], 'wetrakr')

    def test_import_requires_source(self):
        file_obj = SimpleUploadedFile('import.csv', b'collection,media_type,tmdb_id\n', content_type='text/csv')
        response = self.client.post('/api/tracking/data/import/?data_format=csv', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_yamtrack_csv_import_job_creation(self):
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 101, 'status': 'Completed'},
        ])
        file_obj = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')

        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data_format'], 'csv')
        self.assertEqual(response.data.get('source'), 'yamtrack')

    def test_import_rejects_source_format_mismatch(self):
        file_obj = SimpleUploadedFile('trakt-export.zip', self._build_arxmedia_zip(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=trakt', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_data_jobs_list_scoped_and_ordered(self):
        now = timezone.now()
        old_job = DataTransferJob.objects.create(user=self.user, job_type='import', data_format='zip', status='pending')
        new_job = DataTransferJob.objects.create(user=self.user, job_type='export', data_format='zip', status='done')
        DataTransferJob.objects.create(user=self.user2, job_type='import', data_format='zip', status='pending')

        DataTransferJob.objects.filter(id=old_job.id).update(created_at=now - timedelta(days=2))
        DataTransferJob.objects.filter(id=new_job.id).update(created_at=now)

        response = self.client.get('/api/tracking/data/jobs/')
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], new_job.id)
        self.assertEqual(results[1]['id'], old_job.id)

    def _run_import_pipeline(self, job_id):
        """Run the whole import locally: every queued stage executes inline."""
        from arxmedia.celery import app
        from tracking.tasks import run_import_job

        eager = {'CELERY_TASK_ALWAYS_EAGER': True, 'CELERY_TASK_EAGER_PROPAGATES': True}
        previous = {key: app.conf.get(key) for key in eager}
        app.conf.update(eager)
        try:
            run_import_job(job_id)
        finally:
            app.conf.update(previous)

    def test_wetrakr_parser_maps_supported_csv_files(self):
        from tracking.tasks.providers.wetrakr import parse_wetrakr_zip

        content = self._build_wetrakr_zip(
            tracklog=[
                {'type': 'movie', 'tmdb_id': 700, 'status': 'watched', 'tracked_at': '2025-02-03T04:05:06Z', 'updated_at': '2026-09-21T08:41:01.768Z'},
                {'type': 'episode', 'tmdb_id': 701, 'season_number': '1', 'episode_number': '2', 'status': 'watched', 'tracked_at': '2025-02-04T00:00:00Z'},
                {'type': 'show', 'tmdb_id': 702, 'status': 'watched', 'tracked_at': '2025-02-05T00:00:00Z'},
                {'type': 'show', 'tmdb_id': 703, 'status': 'waiting', 'tracked_at': '2025-02-06T00:00:00Z'},
                {'type': 'show', 'tmdb_id': 704, 'status': 'discarded', 'tracked_at': '2025-02-07T00:00:00Z'},
                {'type': 'show', 'tmdb_id': 705, 'status': 'plantowatch', 'tracked_at': '2025-02-08T00:00:00Z'},
                {'type': 'movie', 'tmdb_id': 706, 'status': 'plantowatch', 'tracked_at': '2025-02-09T00:00:00Z'},
            ],
            ratings=[
                {'type': 'show', 'tmdb_id': 703, 'rating': '9', 'rated_at': '2026-02-01T00:00:00Z'},
                {'type': 'movie', 'tmdb_id': 707, 'rating': '11', 'rated_at': '2026-02-01T00:00:00Z'},
            ],
            favorites=[{'type': 'show', 'tmdb_id': 708, 'created_at': '2025-02-10T00:00:00Z'}],
            lists=[
                {'list_name': 'Top', 'list_description': 'Imported list', 'type': 'movie', 'tmdb_id': 709, 'rank': '2', 'created_at': '2025-02-11T00:00:00Z'},
                {'list_name': 'Top', 'list_description': 'Imported list', 'type': 'show', 'tmdb_id': 710, 'rank': '1', 'created_at': '2025-02-12T00:00:00Z'},
            ],
        )

        parsed = parse_wetrakr_zip(content)

        self.assertEqual(parsed.report['summary'], {
            'watch_history': 2,
            'watchlist': 2,
            'ratings': 1,
            'lists': 2,
        })
        self.assertEqual(parsed.report['records_seen'], 12)
        self.assertEqual(parsed.report['unsupported_files'], 2)
        self.assertEqual(parsed.report['skipped_invalid_rating'], 1)
        self.assertEqual(len(parsed.unresolved_episodes), 1)
        self.assertFalse(any(record.media_type == 'episode' for record in parsed.watch_entries()))
        movie_entry = next(record for record in parsed.watch_entries() if record.tmdb_id == 700)
        self.assertEqual(movie_entry.watched_at.isoformat(), '2025-02-03T04:05:06+00:00')
        self.assertEqual(
            {(record.tmdb_id, record.status) for record in parsed.statuses()},
            {(702, 'watched'), (703, 'watching'), (704, 'dropped'), (705, 'plan_to_watch'), (706, 'plan_to_watch')},
        )
        favorites = next(record for record in parsed.lists if record.name == 'Favorites (WeTrackr)')
        self.assertEqual(favorites.privacy, 'private')
        self.assertEqual(favorites.items[0].tmdb_id, 708)
        top = next(record for record in parsed.lists if record.name == 'Top')
        self.assertEqual({item.tmdb_id: item.custom_order for item in top.items}, {709: 1, 710: 0})

    def test_wetrakr_resolves_episode_ids_to_exact_parent_shows(self):
        from tracking.import_resolution import episode_parent_map, resolve_episode_records
        from tracking.tasks.providers.wetrakr import parse_wetrakr_zip

        first_show = TVShow.objects.create(tmdb_id=800, name='Shared Show')
        first_season = Season.objects.create(show=first_show, tmdb_id=8000, season_number=1, name='Season 1')
        Episode.objects.create(season=first_season, tmdb_id=80001, episode_number=1, name='First')
        second_show = TVShow.objects.create(tmdb_id=801, name='Shared Show')
        second_season = Season.objects.create(show=second_show, tmdb_id=8010, season_number=1, name='Season 1')
        Episode.objects.create(season=second_season, tmdb_id=80101, episode_number=1, name='Second')
        content = self._build_wetrakr_zip(
            tracklog=[
                {'type': 'show', 'title': 'Shared Show', 'tmdb_id': 800, 'status': 'watched'},
                {'type': 'show', 'title': 'Shared Show', 'tmdb_id': 801, 'status': 'watched'},
                {'type': 'episode', 'show_title': 'Deliberately Wrong Title', 'tmdb_id': 80001, 'season_number': '1', 'episode_number': '1', 'status': 'watched'},
                {'type': 'episode', 'show_title': 'Deliberately Wrong Title', 'tmdb_id': 80101, 'season_number': '1', 'episode_number': '1', 'status': 'watched'},
            ],
        )

        parsed = parse_wetrakr_zip(content)
        resolved = resolve_episode_records(
            parsed,
            episode_parent_map({record.episode_tmdb_id for record in parsed.unresolved_episodes}),
        )

        self.assertEqual(
            {(record.tmdb_id, record.season_number, record.episode_number) for record in resolved.watch_entries()},
            {(800, 1, 1), (801, 1, 1)},
        )
        self.assertEqual(resolved.report['resolved_episode_records'], 2)
        self.assertEqual(resolved.report['unresolved_episode_records'], 0)

    def test_wetrakr_pre_resolution_syncs_candidates_then_uses_episode_id(self):
        from django.core.files.base import ContentFile

        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            source='wetrakr',
            status='processing',
            import_mode='new_items',
        )
        job.input_file.save('wetrakr.zip', ContentFile(self._build_wetrakr_zip(
            tracklog=[
                {'type': 'show', 'title': 'Candidate Show', 'tmdb_id': 900, 'status': 'watched'},
                {'type': 'episode', 'show_title': 'Deliberately Wrong Title', 'tmdb_id': 90001, 'season_number': '1', 'episode_number': '1', 'status': 'watched'},
            ],
        )), save=True)
        self.addCleanup(job.input_file.delete, save=False)

        def fake_sync(show_id, **kwargs):
            show, _ = TVShow.objects.get_or_create(tmdb_id=show_id, defaults={'name': 'Candidate Show'})
            season, _ = Season.objects.get_or_create(show=show, season_number=1, defaults={'tmdb_id': 9000, 'name': 'Season 1'})
            Episode.objects.get_or_create(season=season, episode_number=1, defaults={'tmdb_id': 90001, 'name': 'Episode 1'})
            return show

        with patch('media.tmdb.tmdb.sync_tv_show', side_effect=fake_sync) as sync:
            self._run_import_pipeline(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(sync.call_args_list[0].args, (900,))
        self.assertTrue(
            WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=900, season_number=1, episode_number=1).exists()
        )
        self.assertNotIn('pipeline', job.metadata)

    def test_import_finishes_when_an_item_fails(self):
        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 701},
                {'media_type': 'movie', 'tmdb_id': 702},
            ],
            'watchlist': [],
            'ratings': [],
        }
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.status = 'processing'
        job.import_mode = 'new_items'
        job.save(update_fields=['status', 'import_mode', 'updated_at'])

        from tracking import import_engine

        real_apply = import_engine.apply_item_records

        def flaky_apply(user, media_type, tmdb_id, records, mode):
            if tmdb_id == 701:
                raise RuntimeError('boom')
            return real_apply(user, media_type, tmdb_id, records, mode)

        with patch('tracking.tasks.import_pipeline.apply_item_records', side_effect=flaky_apply):
            self._run_import_pipeline(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=702).exists())
        self.assertFalse(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=701).exists())

    def test_wetrakr_does_not_guess_an_unresolved_episode_parent(self):
        from tracking.import_resolution import episode_parent_map, resolve_episode_records
        from tracking.tasks.providers.wetrakr import parse_wetrakr_zip

        content = self._build_wetrakr_zip(
            tracklog=[
                {'type': 'show', 'title': 'Uncached Show', 'tmdb_id': 900, 'status': 'watched'},
                {'type': 'episode', 'show_title': 'Uncached Show', 'tmdb_id': 90001, 'season_number': '1', 'episode_number': '1', 'status': 'watched'},
            ],
        )
        parsed = parse_wetrakr_zip(content)

        resolved = resolve_episode_records(parsed, episode_parent_map({90001}))

        self.assertEqual(resolved.watch_entries(), ())
        self.assertEqual(resolved.report['unresolved_episode_records'], 1)
        self.assertIn('unresolved_episode', {warning['code'] for warning in resolved.report['warnings']})

    def test_wetrakr_parser_rejects_csv_files_in_a_folder(self):
        from tracking.tasks.providers.wetrakr import parse_wetrakr_zip

        content = self._build_wetrakr_zip(prefix='wetrakr_export_user/')

        with self.assertRaisesMessage(ValueError, 'must be stored at the ZIP root'):
            parse_wetrakr_zip(content)

    def test_wetrakr_missing_tracked_at_is_an_unknown_watch_date(self):
        from tracking.tasks.providers.wetrakr import parse_wetrakr_zip

        content = self._build_wetrakr_zip(
            tracklog=[
                {'type': 'movie', 'tmdb_id': 710, 'status': 'watched', 'tracked_at': '', 'updated_at': '2026-09-21T08:41:01.768Z'},
                {'type': 'episode', 'tmdb_id': 711, 'season_number': '1', 'episode_number': '2', 'status': 'watched', 'tracked_at': '', 'updated_at': '2026-09-21T08:41:01.768Z'},
            ],
        )
        parsed = parse_wetrakr_zip(content)

        self.assertIsNone(parsed.watch_entries()[0].watched_at)
        self.assertIsNone(parsed.unresolved_episodes[0].watched_at)

    def test_prepare_zip_import_sets_awaiting_confirmation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps([
                {'type': 'movie', 'movie': {'ids': {'tmdb': 100}}, 'watched_at': '2026-07-01T10:00:00.000Z'}
            ]))
            archive.writestr('lists-watchlist.json', json.dumps([
                {'type': 'movie', 'movie': {'ids': {'tmdb': 200}}}
            ]))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_import_job
        prepare_import_job(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'awaiting_confirmation')
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.metadata.get('summary', {}).get('watch_history'), 1)
        self.assertEqual(job.metadata.get('summary', {}).get('watchlist'), 1)

    def test_prepare_wetrakr_zip_sets_awaiting_confirmation(self):
        upload = SimpleUploadedFile(
            'wetrakr_export_user.zip',
            self._build_wetrakr_zip(
                tracklog=[
                    {'type': 'movie', 'tmdb_id': 100, 'status': 'watched', 'tracked_at': '2026-01-01T00:00:00Z'},
                    {'type': 'episode', 'tmdb_id': 200, 'season_number': '1', 'episode_number': '1', 'status': 'watched', 'tracked_at': '2026-01-02T00:00:00Z'},
                ],
                ratings=[{'type': 'movie', 'tmdb_id': 100, 'rating': '8', 'rated_at': '2026-01-01T00:00:00Z'}],
                favorites=[{'type': 'show', 'tmdb_id': 300, 'created_at': '2026-01-03T00:00:00Z'}],
            ),
            content_type='application/zip',
        )
        response = self.client.post(
            '/api/tracking/data/import/?data_format=zip&source=wetrakr',
            {'file': upload},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_import_job

        prepare_import_job(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'awaiting_confirmation')
        self.assertEqual(job.total_items, 4)
        self.assertEqual(job.metadata['summary'], {
            'watch_history': 2,
            'watchlist': 0,
            'ratings': 1,
            'lists': 1,
        })

    def test_wetrakr_import_pipeline_applies_history_statuses_ratings_and_lists(self):
        show = TVShow.objects.create(tmdb_id=200, name='Mapped Show')
        season = Season.objects.create(show=show, tmdb_id=2000, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=20001, episode_number=1, name='Episode 1')
        existing_favorites = CustomList.objects.create(user=self.user, name='Favorites')
        ListItem.objects.create(custom_list=existing_favorites, media_type='movie', tmdb_id=999)
        content = self._build_wetrakr_zip(
            tracklog=[
                {'type': 'movie', 'tmdb_id': 100, 'status': 'watched', 'tracked_at': '2026-01-01T00:00:00Z'},
                {'type': 'episode', 'tmdb_id': 20001, 'season_number': '1', 'episode_number': '1', 'status': 'watched', 'tracked_at': '2026-01-02T00:00:00Z'},
                {'type': 'show', 'tmdb_id': 201, 'status': 'discarded', 'tracked_at': '2026-01-03T00:00:00Z'},
            ],
            ratings=[{'type': 'movie', 'tmdb_id': 100, 'rating': '8', 'rated_at': '2026-01-01T00:00:00Z'}],
            favorites=[{'type': 'show', 'tmdb_id': 300, 'created_at': '2026-01-04T00:00:00Z'}],
            lists=[{'list_name': 'Owned', 'type': 'movie', 'tmdb_id': 400, 'rank': '1', 'created_at': '2026-01-05T00:00:00Z'}],
        )
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='processing',
            input_file=SimpleUploadedFile('wetrakr_export_user.zip', content, content_type='application/zip'),
            source='wetrakr',
            import_mode='new_items',
            total_items=6,
        )

        self._run_import_pipeline(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=100).exists())
        self.assertTrue(WatchEntry.objects.filter(
            user=self.user,
            media_type='episode',
            tmdb_id=200,
            season_number=1,
            episode_number=1,
        ).exists())
        self.assertTrue(UserMediaStatus.objects.filter(
            user=self.user,
            media_type='tv',
            tmdb_id=201,
            status='dropped',
        ).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=100, score=8).exists())
        favorites = CustomList.objects.get(user=self.user, name='Favorites (WeTrackr)')
        self.assertEqual(favorites.privacy, 'private')
        self.assertTrue(ListItem.objects.filter(custom_list=favorites, media_type='tv', tmdb_id=300).exists())
        existing_favorites.refresh_from_db()
        self.assertEqual(list(existing_favorites.items.values_list('tmdb_id', flat=True)), [999])
        owned = CustomList.objects.get(user=self.user, name='Owned')
        self.assertEqual(owned.items.get().custom_order, 0)

    def test_cancelled_import_item_task_does_not_apply_records(self):
        from tracking.tasks import process_media_item

        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            source='wetrakr',
            status='cancelled',
        )

        process_media_item.run(job.id, {
            'media_type': 'movie',
            'tmdb_id': 9999,
            'records': [{'kind': 'watch_entry', 'media_type': 'movie'}],
        })

        self.assertFalse(WatchEntry.objects.filter(user=self.user, tmdb_id=9999).exists())

    def test_prepare_yamtrack_csv_sets_awaiting_confirmation(self):
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 100, 'status': 'Completed', 'score': '8.4'},
            {'source': 'mal', 'media_type': 'anime', 'media_id': 999, 'status': 'Completed'},
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_import_job
        prepare_import_job(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'awaiting_confirmation')
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.metadata.get('summary', {}).get('watch_history'), 1)
        self.assertEqual(job.metadata.get('summary', {}).get('ratings'), 1)
        self.assertEqual(job.metadata.get('skipped_non_tmdb'), 1)

    def test_confirm_zip_import_requires_awaiting_confirmation(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='pending',
        )
        response = self.client.post(f'/api/tracking/data/jobs/{job.id}/confirm/', {'import_mode': 'new_items'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_cancel_import_job_prevents_confirmation(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='awaiting_confirmation',
            source='trakt',
        )
        response = self.client.post(f'/api/tracking/data/jobs/{job.id}/cancel/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')

        confirm_response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'new_items'},
            format='json',
        )
        self.assertEqual(confirm_response.status_code, 400)

    @patch('tracking.tasks.run_import_job.delay')
    def test_confirm_zip_import_starts_apply_task(self, mock_delay):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='zip',
            status='awaiting_confirmation',
            source='trakt',
            metadata={'total_items': 3, 'summary': {'watch_history': 1, 'watchlist': 1, 'ratings': 1}},
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/api/tracking/data/jobs/{job.id}/confirm/',
                {'import_mode': 'mirror_imported_set'},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertTrue(job.overwrite_existing)
        self.assertEqual(job.import_mode, 'mirror_imported_set')
        mock_delay.assert_called_once_with(job.id)

    @patch('tracking.tasks.run_import_job.delay')
    def test_confirm_yamtrack_csv_starts_apply_task(self, mock_delay):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            source='yamtrack',
            metadata={
                'total_items': 2,
                'summary': {'watch_history': 1, 'watchlist': 0, 'ratings': 1},
            },
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/api/tracking/data/jobs/{job.id}/confirm/',
                {'import_mode': 'update_existing'},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertTrue(job.overwrite_existing)
        self.assertEqual(job.import_mode, 'update_existing')
        mock_delay.assert_called_once_with(job.id)

    def test_confirm_mismatched_source_format_is_rejected(self):
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='awaiting_confirmation',
            source='arxmedia',
            metadata={'total_items': 1},
        )
        response = self.client.post(
            f'/api/tracking/data/jobs/{job.id}/confirm/',
            {'import_mode': 'new_items'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('error_code'), 'IMPORT_SOURCE_FORMAT_MISMATCH')

    def test_yamtrack_progress_only_episodes_are_watched(self):
        """Regression: yamtrack exports episode watches as progress events with
        no status/end_date. Dates import verbatim — epoch stays epoch."""
        csv_content = self._build_yamtrack_csv([
            # Real One Piece row shape: empty status/end_date, progressed_at set,
            # and a placeholder start_date of 1970-01-01.
            {
                'source': 'tmdb', 'media_type': 'episode', 'media_id': 37854,
                'season_number': 1, 'episode_number': 1,
                'start_date': '1970-01-01 00:00:00+00:00',
                'progressed_at': '1970-01-01 00:00:00+00:00',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='csv', status='processing',
            input_file=upload, source='yamtrack', import_mode='new_items', total_items=1,
        )
        self._run_import_pipeline(job.id)

        entry = WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=37854).first()
        self.assertIsNotNone(entry)
        self.assertEqual((entry.season_number, entry.episode_number), (1, 1))
        self.assertEqual(
            entry.watched_at,
            datetime(1970, 1, 1, tzinfo=UTC),
        )

    def test_yamtrack_multi_episode_show_creates_every_entry(self):
        """Regression: an item with many episode records must materialize one
        watch entry per episode, not just the latest one."""
        episodes = [
            {
                'source': 'tmdb', 'media_type': 'episode', 'media_id': 37854,
                'season_number': season, 'episode_number': episode,
                'progressed_at': f'1970-01-01 00:00:{episode:02d}+00:00',
            }
            for season in (1, 2)
            for episode in (1, 2, 3)
        ]
        csv_content = self._build_yamtrack_csv(episodes)
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='csv', status='processing',
            input_file=upload, source='yamtrack', import_mode='new_items', total_items=6,
        )
        self._run_import_pipeline(job.id)

        created = WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=37854)
        self.assertEqual(created.count(), 6)

    def test_yamtrack_movie_dropped_imports_dropped_status(self):
        csv_content = self._build_yamtrack_csv([
            {
                'source': 'tmdb', 'media_type': 'movie', 'media_id': 610,
                'status': 'Dropped', 'end_date': '2026-01-05 00:00:00+00:00',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='csv', status='processing',
            input_file=upload, source='yamtrack', import_mode='new_items', total_items=1,
        )
        self._run_import_pipeline(job.id)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='movie', tmdb_id=610)
        self.assertEqual(status_row.status, 'dropped')
        self.assertIsNotNone(status_row.dropped_at)

    def test_yamtrack_tv_dropped_preserved_with_refreshed_counts(self):
        show = TVShow.objects.create(tmdb_id=620, name='Dropped Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=621, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=622, episode_number=1, name='E1', air_date=timezone.localdate() - timedelta(days=1))

        csv_content = self._build_yamtrack_csv([
            {
                'source': 'tmdb', 'media_type': 'episode', 'media_id': 620,
                'season_number': 1, 'episode_number': 1,
                'status': 'Completed', 'end_date': '2026-02-01 10:00:00+00:00',
            },
            {
                'source': 'tmdb', 'media_type': 'tv', 'media_id': 620,
                'status': 'Dropped',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='csv', status='processing',
            input_file=upload, source='yamtrack', import_mode='new_items', total_items=2,
        )
        self._run_import_pipeline(job.id)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=620)
        self.assertEqual(status_row.status, 'dropped')
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertIsNotNone(status_row.dropped_at)

    def test_apply_yamtrack_csv_import_maps_statuses_and_filters_rows(self):
        TVShow.objects.create(tmdb_id=500, name='Mapped Show')
        csv_content = self._build_yamtrack_csv([
            {
                'source': 'tmdb',
                'media_type': 'tv',
                'media_id': 500,
                'status': 'Paused',
                'score': '7.6',
                'progress': '12',
                'progressed_at': '2026-01-05T10:00:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'episode',
                'media_id': 500,
                'season_number': 1,
                'episode_number': 2,
                'status': '',
                'end_date': '2026-02-01T12:30:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'movie',
                'media_id': 601,
                'status': 'Completed',
                'score': '8.5',
                'end_date': '2026-02-03T08:00:00+00:00',
            },
            {
                'source': 'tmdb',
                'media_type': 'movie',
                'media_id': 602,
                'status': 'Planning',
                'score': '0',
            },
            {
                'source': 'mal',
                'media_type': 'movie',
                'media_id': 700,
                'status': 'Completed',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user,
            job_type='import',
            data_format='csv',
            status='processing',
            input_file=upload,
            source='yamtrack',
            import_mode='new_items',
            metadata={'total_items': 5},
            total_items=5,
        )

        self._run_import_pipeline(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.processed_items, job.total_items)
        self.assertEqual(job.metadata.get('skipped_non_tmdb'), 1)

        show_status = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=500)
        self.assertEqual(show_status.status, 'watching')

        episode_entry = WatchEntry.objects.get(
            user=self.user,
            media_type='episode',
            tmdb_id=500,
            season_number=1,
            episode_number=2,
        )
        self.assertEqual(episode_entry.watched_at.isoformat(), '2026-02-01T12:30:00+00:00')

        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=601).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=601, score=9).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='tv', tmdb_id=500, score=8).exists())
        self.assertFalse(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=602).exists())
        self.assertTrue(UserMediaStatus.objects.filter(user=self.user, media_type='movie', tmdb_id=602, status='plan_to_watch').exists())
        self.assertFalse(WatchEntry.objects.filter(user=self.user, tmdb_id=700).exists())

    def test_zip_import_loads_history_watchlist_and_ratings(self):
        watched_history = [
            {
                'type': 'movie',
                'watched_at': '2026-07-01T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 101}},
            },
            {
                'type': 'episode',
                'watched_at': '2026-07-02T10:00:00.000Z',
                'episode': {'season': 2, 'number': 3},
                'show': {'ids': {'tmdb': 202}},
            },
        ]
        watched_movies = [
            {
                'last_watched_at': '2026-07-03T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 303}},
            }
        ]
        watchlist = [
            {'type': 'movie', 'movie': {'ids': {'tmdb': 404}}},
            {'type': 'show', 'show': {'ids': {'tmdb': 505}}},
        ]
        ratings_movies = [
            {'type': 'movie', 'rating': 9, 'rated_at': '2026-07-04T10:00:00.000Z', 'movie': {'ids': {'tmdb': 606}}},
        ]
        ratings_shows = [
            {'type': 'show', 'rating': 8, 'rated_at': '2026-07-05T10:00:00.000Z', 'show': {'ids': {'tmdb': 707}}},
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))
            archive.writestr('watched-movies-1.json', json.dumps(watched_movies))
            archive.writestr('lists-watchlist.json', json.dumps(watchlist))
            archive.writestr('ratings-movies-1.json', json.dumps(ratings_movies))
            archive.writestr('ratings-shows.json', json.dumps(ratings_shows))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import (
            prepare_import_job,
        )

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.metadata.get('report', {}).get('records_seen'), 7)
        self.assertEqual(job.processed_items, job.total_items)

        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=101).exists())
        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=202,
                season_number=2,
                episode_number=3,
            ).exists()
        )
        self.assertTrue(WatchEntry.objects.filter(user=self.user, media_type='movie', tmdb_id=303).exists())

        self.assertTrue(UserMediaStatus.objects.filter(user=self.user, media_type='movie', tmdb_id=404, status='plan_to_watch').exists())
        self.assertTrue(UserMediaStatus.objects.filter(user=self.user, media_type='tv', tmdb_id=505, status='plan_to_watch').exists())

        planned_show = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=505)
        self.assertIsNone(planned_show.started_at)
        self.assertIsNone(planned_show.last_watched_at)

        self.assertTrue(Rating.objects.filter(user=self.user, media_type='movie', tmdb_id=606, score=9).exists())
        self.assertTrue(Rating.objects.filter(user=self.user, media_type='tv', tmdb_id=707, score=8).exists())

        movie_rating = Rating.objects.get(user=self.user, media_type='movie', tmdb_id=606)
        self.assertEqual(movie_rating.created_at.isoformat(), '2026-07-04T10:00:00+00:00')
        self.assertEqual(movie_rating.updated_at.isoformat(), '2026-07-04T10:00:00+00:00')

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_zip_import_supports_watchlist_items_wrapper(self, mock_sync_movie, mock_sync_tv_show):
        watchlist_wrapped = {
            'items': [
                {'type': 'movie', 'movie': {'ids': {'tmdb': 1404}}},
                {'type': 'show', 'show': {'ids': {'tmdb': 1505}}},
            ]
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('lists-watchlist.json', json.dumps(watchlist_wrapped))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import (
            prepare_import_job,
        )

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.metadata.get('report', {}).get('records_seen'), 2)
        self.assertEqual(job.processed_items, job.total_items)
        self.assertEqual(job.metadata.get('summary', {}).get('watchlist'), 2)

        self.assertTrue(UserMediaStatus.objects.filter(user=self.user, media_type='movie', tmdb_id=1404, status='plan_to_watch').exists())
        self.assertTrue(UserMediaStatus.objects.filter(user=self.user, media_type='tv', tmdb_id=1505, status='plan_to_watch').exists())
        self.assertTrue(mock_sync_movie.called)
        self.assertTrue(mock_sync_tv_show.called)

    @patch('tracking.tasks.tmdb.sync_tv_show')
    def test_zip_import_processes_all_files_and_reports_unsupported(self, mock_sync_tv_show):
        watched_history = [
            {
                'type': 'movie',
                'watched_at': '2026-07-01T10:00:00.000Z',
                'movie': {'ids': {'tmdb': 101}},
            },
        ]
        watched_shows = [
            {
                'show': {'ids': {'tmdb': 505}},
                'last_watched_at': '2026-07-01T10:00:00.000Z',
            },
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))
            archive.writestr('watched-shows.json', json.dumps(watched_shows))
            archive.writestr('user-profile.json', json.dumps({'username': 'demo'}))
            archive.writestr('notes-movies.json', json.dumps([]))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import (
            prepare_import_job,
        )

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        job = DataTransferJob.objects.get(id=response.data['id'])
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.metadata.get('report', {}).get('records_seen'), 3)
        self.assertEqual(job.processed_items, job.total_items)
        self.assertGreaterEqual(job.metadata.get('unsupported_files', 0), 2)
        self.assertGreaterEqual(job.metadata.get('unsupported_records', 0), 1)
        self.assertEqual(job.metadata.get('files_failed'), 0)
        # One watch entry applied; the metadata-only show emits no tracking
        # rows and must not inflate the imported count.
        self.assertEqual(job.metadata.get('records_imported', 0), 1)
        self.assertEqual(job.metadata.get('records_skipped', 0), 1)
        self.assertEqual(job.metadata.get('records_unchanged', 0), 0)
        self.assertTrue(mock_sync_tv_show.called)

    def test_new_items_reimport_reports_unchanged_not_imported(self):
        """Regression: re-importing the same file in new_items mode must not
        inflate records_imported; existing rows land in records_unchanged."""
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 610, 'status': 'Completed', 'score': '8.4'},
        ])

        def _run_once():
            upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
            job = DataTransferJob.objects.create(
                user=self.user, job_type='import', data_format='csv', status='processing',
                input_file=upload, source='yamtrack', import_mode='new_items', total_items=1,
            )
            self._run_import_pipeline(job.id)
            job.refresh_from_db()
            return job.metadata.get('report', {})

        first = _run_once()
        # One row fans out to a watch entry plus a rating.
        self.assertEqual(first.get('records_imported'), 2)
        self.assertEqual(first.get('records_skipped'), 0)
        self.assertEqual(first.get('records_unchanged'), 0)

        second = _run_once()
        self.assertEqual(second.get('records_imported'), 0)
        self.assertEqual(second.get('records_skipped'), 0)
        self.assertEqual(second.get('records_unchanged'), 2)

    def test_new_items_reimport_does_not_overwrite_existing_status(self):
        """Regression: explicit statuses in new_items mode must not overwrite
        an existing row via reconciliation."""
        UserMediaStatus.objects.create(
            user=self.user, media_type='movie', tmdb_id=777, status='watched',
        )
        csv_content = self._build_yamtrack_csv([
            {'source': 'tmdb', 'media_type': 'movie', 'media_id': 777, 'status': 'Planning'},
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='csv', status='processing',
            input_file=upload, source='yamtrack', import_mode='new_items', total_items=1,
        )
        self._run_import_pipeline(job.id)

        self.assertEqual(
            UserMediaStatus.objects.get(user=self.user, media_type='movie', tmdb_id=777).status,
            'watched',
        )
        job.refresh_from_db()
        report = job.metadata.get('report', {})
        self.assertEqual(report.get('records_imported'), 0)
        self.assertEqual(report.get('records_unchanged'), 1)

    @patch('tracking.tasks.tmdb.sync_tv_show')
    def test_zip_import_syncs_show_metadata_for_episode_history(self, mock_sync_tv_show):
        TVShow.objects.create(tmdb_id=202, name='Existing Show')
        watched_history = [
            {
                'type': 'episode',
                'watched_at': '2026-07-02T10:00:00.000Z',
                'episode': {'season': 2, 'number': 3},
                'show': {'ids': {'tmdb': 202}},
            },
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('watched-history-1.json', json.dumps(watched_history))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_import_job

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        self.assertTrue(mock_sync_tv_show.called)

    def test_zip_import_maps_hidden_progress_to_dropped_show_status(self):
        hidden_progress = [
            {
                'type': 'show',
                'hidden_at': '2026-07-01T10:00:00.000Z',
                'show': {'ids': {'tmdb': 9090}},
            }
        ]

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hidden-progress-watched.json', json.dumps(hidden_progress))

        upload = SimpleUploadedFile('trakt-export.zip', buffer.getvalue(), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=trakt', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import (
            prepare_import_job,
        )

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        dropped = UserMediaStatus.objects.get(
            user=self.user,
            media_type='tv',
            tmdb_id=9090,
            status='dropped',
        )
        self.assertEqual(dropped.dropped_at.isoformat(), '2026-07-01T10:00:00+00:00')
        self.assertEqual(dropped.status_changed_at.isoformat(), '2026-07-01T10:00:00+00:00')

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_local_import_syncs_metadata_for_items(self, mock_sync_movie, mock_sync_tv_show):
        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 111, 'status': 'watched'},
                {'media_type': 'episode', 'tmdb_id': 222, 'season_number': 1, 'episode_number': 1, 'status': 'watched'},
            ],
            'watchlist': [
                {'media_type': 'tv', 'tmdb_id': 333},
            ],
            'ratings': [
                {'media_type': 'movie', 'tmdb_id': 444, 'score': 8, 'created_at': '2025-01-04T03:04:05Z', 'updated_at': '2025-01-04T03:04:05Z'},
            ],
        }
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import (
            prepare_import_job,
        )

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        self.assertTrue(mock_sync_movie.called)
        self.assertTrue(mock_sync_tv_show.called)

    @patch('tracking.tasks.tmdb.sync_tv_show')
    @patch('tracking.tasks.tmdb.sync_movie')
    def test_local_import_skips_metadata_fetch_when_already_present(self, mock_sync_movie, mock_sync_tv_show):
        Movie.objects.create(tmdb_id=111, title='Existing movie')
        show = TVShow.objects.create(tmdb_id=333, name='Existing show')
        Season.objects.create(show=show, tmdb_id=3331, season_number=1, name='Season 1')

        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 111, 'status': 'watched'},
            ],
            'watchlist': [
                {'media_type': 'tv', 'tmdb_id': 333},
            ],
            'ratings': [],
        }
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        self.assertEqual(response.status_code, 201)

        from tracking.tasks import prepare_import_job

        prepare_import_job(response.data['id'])
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])
        self._run_import_pipeline(response.data['id'])

        mock_sync_movie.assert_not_called()
        mock_sync_tv_show.assert_not_called()

    def test_reconcile_command_repairs_history_without_status_row(self):
        """Regression: imported watch history whose UserMediaStatus row is missing."""

        Movie.objects.create(tmdb_id=8001, title='Orphan Movie')
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=8001, watched_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=8002, status='plan_to_watch')
        UserMediaStatus.objects.filter(media_type='movie', tmdb_id=8001).delete()

        self.assertFalse(UserMediaStatus.objects.filter(media_type='movie', tmdb_id=8001).exists())

        call_command('reconcile_user_media_status', username=self.user.username)

        repaired = UserMediaStatus.objects.get(user=self.user, media_type='movie', tmdb_id=8001)
        self.assertEqual(repaired.status, 'watched')
        self.assertIsNotNone(repaired.last_watched_at)
        # Untouched planning stays.
        self.assertTrue(UserMediaStatus.objects.filter(media_type='movie', tmdb_id=8002, status='plan_to_watch').exists())

    def test_import_pipeline_is_replayable(self):
        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 9101},
                {'media_type': 'episode', 'tmdb_id': 9102, 'season_number': 1, 'episode_number': 1},
            ],
            'watchlist': [
                {'media_type': 'movie', 'tmdb_id': 9103},
            ],
            'ratings': [
                {'media_type': 'movie', 'tmdb_id': 9101, 'score': 7, 'created_at': '2025-01-05T03:04:05Z', 'updated_at': '2025-01-05T03:04:05Z'},
            ],
        }
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        job_id = response.data['id']

        from tracking.tasks import prepare_import_job

        prepare_import_job(job_id)
        job = DataTransferJob.objects.get(id=job_id)
        job.import_mode = 'update_existing'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])

        self._run_import_pipeline(job_id)

        def snapshot():
            job.refresh_from_db()
            return (
                job.status,
                sorted(WatchEntry.objects.filter(user=self.user).values_list('media_type', 'tmdb_id', 'season_number', 'episode_number')),
                sorted(UserMediaStatus.objects.filter(user=self.user).values_list('media_type', 'tmdb_id', 'status')),
                sorted(Rating.objects.filter(user=self.user).values_list('media_type', 'tmdb_id', 'score')),
            )

        first = snapshot()
        self.assertEqual(first[0], 'done')

        # Simulate a retry window: chunks/finalize may re-run while processing.
        DataTransferJob.objects.filter(id=job_id).update(status='processing')
        self._run_import_pipeline(job_id)
        self.assertEqual(snapshot(), first)

    @patch('tracking.tasks.tmdb.sync_movie')
    def test_import_pipeline_completes_many_items(self, mock_sync_movie):
        movies = [{'media_type': 'movie', 'tmdb_id': 7000 + index} for index in range(250)]
        payload = {'watch_history': movies, 'watchlist': [], 'ratings': []}
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        job_id = response.data['id']

        from tracking.tasks import prepare_import_job

        prepare_import_job(job_id)
        job = DataTransferJob.objects.get(id=job_id)
        job.import_mode = 'new_items'
        job.status = 'processing'
        job.save(update_fields=['import_mode', 'status', 'updated_at'])

        self._run_import_pipeline(job_id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.processed_items, job.total_items)
        self.assertEqual(WatchEntry.objects.filter(user=self.user).count(), 250)
        self.assertTrue(mock_sync_movie.called)

    @patch('tracking.tasks.process_media_item.delay')
    def test_run_import_job_dispatches_tv_items_before_movies(self, mock_delay):
        payload = {
            'watch_history': [
                {'media_type': 'movie', 'tmdb_id': 601},
                {'media_type': 'episode', 'tmdb_id': 502, 'season_number': 1, 'episode_number': 1},
            ],
            'watchlist': [{'media_type': 'movie', 'tmdb_id': 603}],
            'ratings': [],
        }
        file_obj = SimpleUploadedFile('arxmedia-export.zip', self._build_arxmedia_zip(payload), content_type='application/zip')
        response = self.client.post('/api/tracking/data/import/?data_format=zip&source=arxmedia', {'file': file_obj}, format='multipart')
        job = DataTransferJob.objects.get(id=response.data['id'])
        job.status = 'processing'
        job.save(update_fields=['status', 'updated_at'])

        from tracking.tasks import run_import_job

        run_import_job(job.id)

        dispatched_types = [call.args[1]['media_type'] for call in mock_delay.call_args_list]
        tv_positions = [i for i, mt in enumerate(dispatched_types) if mt == 'tv']
        movie_positions = [i for i, mt in enumerate(dispatched_types) if mt == 'movie']
        self.assertTrue(tv_positions and movie_positions)
        self.assertLess(max(tv_positions), min(movie_positions))

    @patch('tracking.status_sync.refresh_all_statuses_for_show')
    @patch('tracking.tasks.tmdb.sync_tv_show')
    def test_process_media_item_skips_status_recompute_for_imports(self, mock_sync_tv_show, mock_recompute):
        from tracking.tasks import process_media_item

        job = DataTransferJob.objects.create(
            user=self.user, job_type='import', data_format='zip', status='processing', source='arxmedia',
        )
        process_media_item(job.id, {'media_type': 'tv', 'tmdb_id': 4242, 'records': []}, recompute_status=False)

        self.assertTrue(mock_sync_tv_show.called)
        self.assertFalse(mock_recompute.called)

    def test_up_next_usable_when_import_finishes(self):
        """Episodes materialized during the import must be visible to up_next at done."""
        show = TVShow.objects.create(tmdb_id=4601, name='Ready Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=4602, season_number=1, name='Season 1')
        today = timezone.now().date()
        Episode.objects.create(
            season=season, tmdb_id=4603, episode_number=1, name='Next Up',
            air_date=today - timedelta(days=2), runtime=42,
        )
        Episode.objects.create(
            season=season, tmdb_id=4604, episode_number=2, name='Aired Unwatched',
            air_date=today - timedelta(days=1), runtime=42,
        )

        csv_content = self._build_yamtrack_csv([
            {
                'source': 'tmdb',
                'media_type': 'episode',
                'media_id': 4601,
                'season_number': 1,
                'episode_number': 1,
                'status': 'Completed',
                'end_date': '2026-03-01T10:00:00+00:00',
            },
        ])
        upload = SimpleUploadedFile('yamtrack.csv', csv_content, content_type='text/csv')
        response = self.client.post('/api/tracking/data/import/?data_format=csv&source=yamtrack', {'file': upload}, format='multipart')
        job_id = response.data['id']

        from tracking.tasks import prepare_import_job

        prepare_import_job(job_id)
        DataTransferJob.objects.filter(id=job_id).update(status='processing')
        self._run_import_pipeline(job_id)

        job = DataTransferJob.objects.get(id=job_id)
        self.assertEqual(job.status, 'done')

        up_next = self.client.get('/api/tracking/up-next/')
        self.assertEqual(up_next.status_code, 200)
        self.assertEqual(len(up_next.data), 1)
        self.assertEqual(up_next.data[0]['show_name'], 'Ready Show')
