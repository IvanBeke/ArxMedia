"""Rebuild UserMediaStatus rows from source-of-truth data.

Repairs drift left by earlier import/interaction paths: movies with watch
history but no watched status, shows whose status disagrees with their
entries, and planning rows that history should have superseded.
"""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q
from tracking.choices import MediaType
from tracking.import_engine import reconcile_user_media_status
from tracking.import_records import ParsedImport, StatusRecord, WatchEntryRecord
from tracking.models import UserMediaStatus, WatchEntry


class Command(BaseCommand):
    help = 'Reconcile UserMediaStatus rows from watch history and explicit statuses.'

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument('--username', default=None, help='Limit to one username.')
        parser.add_argument('--dry-run', action='store_true', help='Report what would change without writing.')

    def handle(self, *args: Any, **options: Any):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        users = user_model.objects.all()
        if options['username']:
            users = users.filter(username=options['username'])

        dry_run = options['dry_run']
        total_fixed = 0
        for user in users.iterator():
            parsed = self._build_parsed_import(user)
            before = self._snapshot(user)
            if not parsed.records and not before:
                continue
            if dry_run:
                self.stdout.write(f'[dry-run] {user.username}: would reconcile {len(parsed.records)} items')
                total_fixed += len(parsed.records)
                continue
            reconcile_user_media_status(user, parsed)
            after = self._snapshot(user)
            changed = sum(1 for key in set(before) | set(after) if before.get(key) != after.get(key))
            total_fixed += changed
            self.stdout.write(f'{user.username}: reconciled {changed} status rows')

        verb = 'would reconcile' if dry_run else 'reconciled'
        self.stdout.write(self.style.SUCCESS(f'Done. {verb} {total_fixed} status rows.'))

    def _build_parsed_import(self, user) -> ParsedImport:
        """Derive records from both source-of-truth tables: watch history and
        explicit statuses. Reconciliation then re-imposes canonical state."""
        records: list[StatusRecord | WatchEntryRecord] = []
        statuses = UserMediaStatus.objects.for_user(user).filter(
            Q(media_type=MediaType.MOVIE) | Q(media_type=MediaType.TV)
        )
        for row in statuses.iterator():
            records.append(StatusRecord(media_type=row.media_type, tmdb_id=row.tmdb_id, status=row.status, status_at=row.status_changed_at))
        for entry in WatchEntry.objects.filter(user=user).iterator():
            records.append(
                WatchEntryRecord(
                    media_type=entry.media_type,
                    tmdb_id=entry.tmdb_id,
                    watched_at=entry.watched_at or entry.created_at,
                    season_number=entry.season_number,
                    episode_number=entry.episode_number,
                )
            )
        return ParsedImport(records=tuple(records), collections_present=frozenset(), invalid_count=0, report={})

    def _snapshot(self, user) -> dict:
        return {
            (row.media_type, row.tmdb_id): row.status
            for row in UserMediaStatus.objects.for_user(user).iterator()
        }
