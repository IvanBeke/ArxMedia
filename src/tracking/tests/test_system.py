import io
from datetime import timedelta
from unittest.mock import patch

from celery.schedules import crontab
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from media.tmdb import TMDBNotFoundError
from tracking.models import (
    DataTransferJob,
)

from .base import User


class SystemTaskTests(TestCase):
    def test_cleanup_data_transfer_jobs_removes_stale_rows_and_files(self):
        import os

        from django.core.files.base import ContentFile

        from tracking.tasks.system import cleanup_data_transfer_jobs

        user = User.objects.create_user(username='cleanupuser', email='cleanup@example.com', password='testpass123')

        old_import = DataTransferJob.objects.create(user=user, job_type='import', data_format='zip', status='done', source='trakt')
        old_import.input_file.save('old-import.zip', ContentFile(b'import-bytes'), save=True)
        old_import_path = old_import.input_file.path
        DataTransferJob.objects.filter(id=old_import.id).update(created_at=timezone.now() - timedelta(days=8))

        recent_import = DataTransferJob.objects.create(user=user, job_type='import', data_format='zip', status='done', source='trakt')
        recent_import.input_file.save('recent-import.zip', ContentFile(b'import-bytes'), save=True)

        fileless_export = DataTransferJob.objects.create(user=user, job_type='export', data_format='zip', status='done')

        live_export = DataTransferJob.objects.create(user=user, job_type='export', data_format='zip', status='processing')

        kept_export = DataTransferJob.objects.create(user=user, job_type='export', data_format='zip', status='done')
        kept_export.output_file.save('kept-export.zip', ContentFile(b'zip-bytes'), save=True)

        stuck_import = DataTransferJob.objects.create(user=user, job_type='import', data_format='zip', status='processing', source='trakt')
        DataTransferJob.objects.filter(id=stuck_import.id).update(created_at=timezone.now() - timedelta(days=8))

        result = cleanup_data_transfer_jobs()

        self.assertEqual(result, {'exports_removed': 1, 'imports_removed': 1})
        self.assertFalse(DataTransferJob.objects.filter(id=old_import.id).exists())
        self.assertFalse(os.path.exists(old_import_path))
        self.assertTrue(DataTransferJob.objects.filter(id=recent_import.id).exists())
        self.assertFalse(DataTransferJob.objects.filter(id=fileless_export.id).exists())
        self.assertTrue(DataTransferJob.objects.filter(id=live_export.id).exists())
        self.assertTrue(DataTransferJob.objects.filter(id=kept_export.id).exists())
        self.assertTrue(DataTransferJob.objects.filter(id=stuck_import.id).exists())

    @patch('tracking.tasks.system.sync_tmdb_metadata_item.delay')
    @patch('tracking.tasks.system.tmdb.get_tv_changes')
    @patch('tracking.tasks.system.tmdb.get_movie_changes')
    def test_sync_tmdb_changed_items_queues_one_task_per_local_item(
        self,
        mock_get_movie_changes,
        mock_get_tv_changes,
        mock_item_delay,
    ):
        Movie.objects.create(tmdb_id=11, title='Local movie')
        TVShow.objects.create(tmdb_id=22, name='Local show')

        mock_get_movie_changes.side_effect = [
            {'results': [{'id': 11}, {'id': 999}], 'total_pages': 2},
            {'results': [{'id': 888}], 'total_pages': 2},
        ]
        mock_get_tv_changes.return_value = {'results': [{'id': 22}, {'id': 777}], 'total_pages': 1}

        from tracking.tasks.system import sync_tmdb_changed_items

        result = sync_tmdb_changed_items()

        self.assertEqual(result['movie_changed_total'], 3)
        self.assertEqual(result['tv_changed_total'], 2)
        self.assertEqual((result['movies_queued'], result['tv_queued']), (1, 1))
        self.assertEqual([call.args for call in mock_item_delay.call_args_list], [('movie', 11), ('tv', 22)])
        for call in mock_get_movie_changes.call_args_list + mock_get_tv_changes.call_args_list:
            self.assertFalse(call.kwargs['use_cache'])

    @patch('tracking.tasks.system.sync_show_episode_credits.delay')
    @patch('tracking.tasks.system.tmdb.sync_tv_show')
    @patch('tracking.tasks.system.tmdb.sync_movie')
    def test_sync_tmdb_metadata_item_bypasses_cache_and_refreshes_show_credits(
        self, mock_sync_movie, mock_sync_tv_show, mock_credits_delay,
    ):
        from tracking.tasks.system import sync_tmdb_metadata_item

        result_movie = sync_tmdb_metadata_item('movie', 11)
        result_tv = sync_tmdb_metadata_item('tv', 22)

        self.assertEqual((result_movie['status'], result_tv['status']), ('ok', 'ok'))
        mock_sync_movie.assert_called_once_with(11, use_cache=False)
        mock_sync_tv_show.assert_called_once_with(22, use_cache=False)
        mock_credits_delay.assert_called_once_with(22, None, False)

    @patch('tracking.tasks.system.sync_show_episode_credits.delay')
    @patch('tracking.tasks.system.tmdb.sync_tv_show', side_effect=TMDBNotFoundError('gone'))
    def test_sync_tmdb_metadata_item_skips_items_removed_from_tmdb(self, mock_sync_tv_show, mock_credits_delay):
        from tracking.tasks.system import sync_tmdb_metadata_item

        self.assertEqual(sync_tmdb_metadata_item('tv', 23)['status'], 'not_found')
        mock_credits_delay.assert_not_called()

    @patch('tracking.tasks.system.tmdb.get_episode_credits')
    def test_sync_show_episode_credits_syncs_all_local_episodes(self, mock_sync_credits):
        from tracking.tasks.system import sync_show_episode_credits

        show = TVShow.objects.create(tmdb_id=4444, name='Credits Task Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=44441, season_number=1, name='Season 1')
        season.episodes.create(tmdb_id=444411, episode_number=1, name='Episode 1')
        season.episodes.create(tmdb_id=444412, episode_number=2, name='Episode 2')

        def fake_credits(show_id, season_number, episode_number, **kwargs):
            if episode_number == 1:
                raise RuntimeError('boom')
            return {'cast': []}

        mock_sync_credits.side_effect = fake_credits

        result = sync_show_episode_credits(4444)

        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['episode_credits_synced'], 1)
        self.assertEqual(result['episode_credit_failures'], 1)
        called_triplets = sorted((c.args[0], c.args[1], c.args[2]) for c in mock_sync_credits.call_args_list)
        self.assertEqual(called_triplets, [(4444, 1, 1), (4444, 1, 2)])
        for call in mock_sync_credits.call_args_list:
            self.assertIs(call.kwargs['use_cache'], False)

    @patch('tracking.tasks.system.tmdb.get_episode_credits', return_value={'cast': []})
    def test_sync_show_episode_credits_limits_to_seasons_and_uses_cache(self, mock_get_credits):
        from tracking.tasks.system import sync_show_episode_credits

        show = TVShow.objects.create(tmdb_id=4445, name='Scoped Show')
        for number in (1, 2):
            season = Season.objects.create(show=show, tmdb_id=44450 + number, season_number=number, name=f'S{number}')
            Episode.objects.create(season=season, tmdb_id=444500 + number, episode_number=1, name='E1')

        result = sync_show_episode_credits(4445, [2], True)

        self.assertEqual(result['episode_credits_synced'], 1)
        self.assertEqual([call.args[1] for call in mock_get_credits.call_args_list], [2])
        self.assertIs(mock_get_credits.call_args.kwargs['use_cache'], True)

    @patch('tracking.tasks.system.tmdb.get_episode_credits')
    def test_sync_show_episode_credits_skips_missing_show(self, mock_sync_credits):
        from tracking.tasks.system import sync_show_episode_credits

        result = sync_show_episode_credits(987654)

        self.assertEqual(result['status'], 'missing')
        mock_sync_credits.assert_not_called()

    def test_celery_beat_schedule_runs_tmdb_sync_every_six_hours(self):
        schedule_config = settings.CELERY_BEAT_SCHEDULE['tracking-sync-tmdb-changed-items']

        self.assertEqual(schedule_config['task'], 'tracking.sync_tmdb_changed_items')
        self.assertIsInstance(schedule_config['schedule'], crontab)
        self.assertEqual(schedule_config['schedule']._orig_hour, '*/6')
        self.assertIn(schedule_config['schedule']._orig_minute, (0, '0'))


class SyncTmdbChangedItemsCommandTests(TestCase):
    @patch('tracking.management.commands.sync_tmdb_changed_items.sync_tmdb_changed_items_for_window')
    @patch('tracking.management.commands.sync_tmdb_changed_items.timezone.localdate')
    def test_command_uses_default_window(self, mock_localdate, mock_sync):
        mock_localdate.return_value = timezone.datetime(2026, 8, 17).date()
        mock_sync.return_value = {'ok': 1}

        out = io.StringIO()
        call_command('sync_tmdb_changed_items', stdout=out)

        self.assertEqual(out.getvalue().strip(), '{"ok": 1}')
        mock_sync.assert_called_once_with(
            timezone.datetime(2026, 8, 16).date(),
            timezone.datetime(2026, 8, 17).date(),
        )

    @patch('tracking.management.commands.sync_tmdb_changed_items.sync_tmdb_changed_items_for_window')
    def test_command_accepts_custom_window(self, mock_sync):
        mock_sync.return_value = {'movies_synced': 2}

        out = io.StringIO()
        call_command(
            'sync_tmdb_changed_items',
            '--start-date=2026-08-01',
            '--end-date=2026-08-10',
            stdout=out,
        )

        mock_sync.assert_called_once_with(
            timezone.datetime(2026, 8, 1).date(),
            timezone.datetime(2026, 8, 10).date(),
        )

    def test_command_rejects_invalid_date(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-13-01')

    def test_command_rejects_start_after_end(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-08-10', '--end-date=2026-08-01')

    def test_command_rejects_window_longer_than_14_days(self):
        with self.assertRaises(CommandError):
            call_command('sync_tmdb_changed_items', '--start-date=2026-08-01', '--end-date=2026-08-20')
