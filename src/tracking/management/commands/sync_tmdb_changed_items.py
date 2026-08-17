import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from tracking.tasks.system import sync_tmdb_changed_items_for_window


class Command(BaseCommand):
    help = 'Sync locally stored TMDB items that changed in a given date window.'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
        parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')

    def handle(self, *args, **options):
        today = timezone.localdate()
        default_start = today - timedelta(days=1)

        start_date = self._parse_date(options.get('start_date'), 'start-date') if options.get('start_date') else default_start
        end_date = self._parse_date(options.get('end_date'), 'end-date') if options.get('end_date') else today

        if start_date > end_date:
            raise CommandError('--start-date must be less than or equal to --end-date.')

        if (end_date - start_date).days > 13:
            raise CommandError('TMDB changes endpoints support a maximum 14-day window.')

        result = sync_tmdb_changed_items_for_window(start_date, end_date)
        self.stdout.write(json.dumps(result, sort_keys=True))

    def _parse_date(self, value: str, option_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(f'Invalid date for --{option_name}: {value}') from exc
