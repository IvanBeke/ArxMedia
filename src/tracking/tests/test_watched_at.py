from datetime import UTC, date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class WatchedAtResolutionTests(BaseTestCase):
    """Clients send a watched_at token or timestamp; the backend turns it into the stored moment."""

    def test_episode_release_date_uses_broadcast_time_and_is_returned(self):
        show = TVShow.objects.create(tmdb_id=340, name='Token Show')
        season = Season.objects.create(show=show, tmdb_id=3401, season_number=1, name='S1')
        broadcast = datetime(2023, 5, 4, 20, 30, tzinfo=UTC)
        Episode.objects.create(season=season, tmdb_id=34011, episode_number=1, name='E1', air_date=date(2023, 5, 4), broadcast_start=broadcast)

        response = self.client.post(
            '/api/tracking/episodes/mark/',
            {'tmdb_id': 340, 'season_number': 1, 'episode_number': 1, 'watched_at': 'release_date'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['watched_at'], broadcast)
        self.assertEqual(WatchEntry.objects.get(user=self.user, tmdb_id=340).watched_at, broadcast)

    def test_movie_release_date_and_missing_release_fallback(self):
        Movie.objects.create(tmdb_id=341, title='Dated', release_date=date(2010, 7, 16))
        Movie.objects.create(tmdb_id=342, title='Undated', release_date=None)
        before = timezone.now()

        dated = self.client.post('/api/tracking/history/', {'media_type': 'movie', 'tmdb_id': 341, 'watched_at': 'release_date'}, format='json')
        undated = self.client.post('/api/tracking/history/', {'media_type': 'movie', 'tmdb_id': 342, 'watched_at': 'release_date'}, format='json')

        self.assertEqual(dated.status_code, 201)
        self.assertEqual(timezone.localtime(WatchEntry.objects.get(tmdb_id=341).watched_at).date(), date(2010, 7, 16))
        self.assertEqual(undated.status_code, 201)
        self.assertGreaterEqual(WatchEntry.objects.get(tmdb_id=342).watched_at, before)

    def test_unknown_now_and_explicit_timestamps(self):
        before = timezone.now()
        for tmdb_id, value in ((343, 'unknown'), (344, 'now'), (345, None), (346, '2022-02-02T10:00:00Z')):
            payload = {'media_type': 'movie', 'tmdb_id': tmdb_id}
            if value is not None:
                payload['watched_at'] = value
            self.assertEqual(self.client.post('/api/tracking/history/', payload, format='json').status_code, 201)

        self.assertIsNone(WatchEntry.objects.get(tmdb_id=343).watched_at)
        self.assertGreaterEqual(WatchEntry.objects.get(tmdb_id=344).watched_at, before)
        self.assertGreaterEqual(WatchEntry.objects.get(tmdb_id=345).watched_at, before)
        self.assertEqual(WatchEntry.objects.get(tmdb_id=346).watched_at, datetime(2022, 2, 2, 10, 0, tzinfo=UTC))

    def test_invalid_watched_at_is_rejected_without_writing(self):
        for url, payload in (
            ('/api/tracking/history/', {'media_type': 'movie', 'tmdb_id': 347}),
            ('/api/tracking/episodes/mark/', {'tmdb_id': 347, 'season_number': 1, 'episode_number': 1}),
        ):
            with self.subTest(url=url):
                response = self.client.post(url, {**payload, 'watched_at': 'yesterday-ish'}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('watched_at', response.data)
        self.assertFalse(WatchEntry.objects.filter(user=self.user, tmdb_id=347).exists())


class UnknownWatchDateTests(BaseTestCase):
    """A null watched_at means the watch date is unknown."""

    def test_history_sorts_unknown_dates_as_the_oldest(self):
        older = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=360, watched_at=timezone.now() - timedelta(days=5))
        newer = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=361, watched_at=timezone.now())
        unknown = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=362, watched_at=None)

        newest_first = [row['id'] for row in self.client.get('/api/tracking/history/').data['results']]
        oldest_first = [row['id'] for row in self.client.get('/api/tracking/history/', {'order': 'oldest'}).data['results']]

        self.assertEqual(newest_first, [newer.id, older.id, unknown.id])
        self.assertEqual(oldest_first, [unknown.id, older.id, newer.id])

    def test_recent_activity_lists_unknown_dates_last(self):
        dated = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=363, watched_at=timezone.now() - timedelta(days=30))
        unknown = WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=364, watched_at=None)

        recent = self.client.get('/api/tracking/stats/').data['recent_activity']

        self.assertEqual([row['id'] for row in recent], [dated.id, unknown.id])

    def test_heatmap_leaves_out_unknown_dates(self):
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=365, watched_at=timezone.now())
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=366, watched_at=None)

        response = self.client.get(f'/api/auth/users/{self.user.username}/activity/')

        self.assertEqual(response.data['total'], 1)

    def test_show_status_dates_ignore_unknown_watches(self):
        show = TVShow.objects.create(tmdb_id=367, name='Mixed Dates', status='Returning Series')
        season = Season.objects.create(show=show, tmdb_id=3671, season_number=1, name='S1')
        for number in (1, 2):
            Episode.objects.create(season=season, tmdb_id=36710 + number, episode_number=number, name=f'E{number}', air_date=date(2020, 1, number))
        dated = timezone.now() - timedelta(days=2)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=367, season_number=1, episode_number=1, watched_at=dated)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=367, season_number=1, episode_number=2, watched_at=None)

        row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=367)

        self.assertEqual(row.watched_episodes, 2)
        self.assertEqual(row.started_at, dated)
        self.assertEqual(row.last_watched_at, dated)

    def test_movie_with_unknown_watch_date_is_watched_without_dates(self):
        before = timezone.now()
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=368, watched_at=None)

        row = UserMediaStatus.objects.get(user=self.user, media_type='movie', tmdb_id=368)

        self.assertEqual(row.status, 'watched')
        self.assertIsNone(row.last_watched_at)
        self.assertIsNone(row.completed_at)
        self.assertGreaterEqual(row.status_changed_at, before)


class UnknownWatchDateMigrationTests(TransactionTestCase):
    def _targets(self, tracking_migration):
        executor = MigrationExecutor(connection)
        others = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracking']
        return [('tracking', tracking_migration), *others]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migration_turns_the_epoch_marker_into_null(self):
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        before = self._targets('0031_watch_entry_history_indexes')
        after = self._targets('0032_unknown_watched_at_as_null')
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        user = old_apps.get_model('accounts', 'User').objects.create(username='epoch-user')
        OldWatchEntry = old_apps.get_model('tracking', 'WatchEntry')
        OldStatus = old_apps.get_model('tracking', 'UserMediaStatus')
        legacy_null = OldWatchEntry.objects.create(user=user, media_type='movie', tmdb_id=1, watched_at=None)
        unknown = OldWatchEntry.objects.create(user=user, media_type='movie', tmdb_id=2, watched_at=epoch)
        dated_at = datetime(2024, 3, 1, tzinfo=UTC)
        dated = OldWatchEntry.objects.create(user=user, media_type='movie', tmdb_id=3, watched_at=dated_at)
        status = OldStatus.objects.create(
            user=user, media_type='tv', tmdb_id=4, status='dropped',
            dropped_at=epoch, status_changed_at=epoch, last_watched_at=epoch, started_at=epoch,
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(after)

        self.assertEqual(WatchEntry.objects.get(id=legacy_null.id).watched_at, WatchEntry.objects.get(id=legacy_null.id).created_at)
        self.assertIsNone(WatchEntry.objects.get(id=unknown.id).watched_at)
        self.assertEqual(WatchEntry.objects.get(id=dated.id).watched_at, dated_at)
        migrated = UserMediaStatus.objects.get(id=status.id)
        self.assertIsNone(migrated.last_watched_at)
        self.assertIsNone(migrated.started_at)
        self.assertEqual(migrated.dropped_at, migrated.created_at)
        self.assertEqual(migrated.status_changed_at, migrated.created_at)


class UniqueEpisodeWatchMigrationTests(TransactionTestCase):
    def _targets(self, tracking_migration):
        executor = MigrationExecutor(connection)
        others = [node for node in executor.loader.graph.leaf_nodes() if node[0] != 'tracking']
        return [('tracking', tracking_migration), *others]

    def setUp(self):
        self.before = self._targets('0029_private_data_transfer_paths')
        self.after = self._targets('0030_unique_episode_watch_entries')

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migration_keeps_earliest_episode_watch_and_adds_constraint(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps
        OldUser = old_apps.get_model('accounts', 'User')
        OldWatchEntry = old_apps.get_model('tracking', 'WatchEntry')
        user = OldUser.objects.create(username='dup-user')
        first = timezone.now() - timedelta(days=3)
        kept = OldWatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=1, season_number=1, episode_number=1, watched_at=first,
        )
        for watched_at in (first + timedelta(days=1), None):
            OldWatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=1, season_number=1, episode_number=1, watched_at=watched_at,
            )
        other = OldWatchEntry.objects.create(
            user=user, media_type='episode', tmdb_id=1, season_number=1, episode_number=2, watched_at=first,
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)

        self.assertEqual(
            set(WatchEntry.objects.filter(user_id=user.id).values_list('id', flat=True)),
            {kept.id, other.id},
        )
        with self.assertRaises(IntegrityError):
            WatchEntry.objects.create(
                user_id=user.id, media_type='episode', tmdb_id=1, season_number=1, episode_number=1,
            )
