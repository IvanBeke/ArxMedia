from django.db.models import Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from tracking.models import WatchEntry

from .entries import EPISODE_ENTRY, MOVIE_ENTRY, watch_minutes, year_bounds


def monthly_stats(user_id, year=None):
    """Watch time per month of a calendar year (the current one by default), split by movies and episodes, in a single query.

    Entries with an unknown watch date are left out. Months without entries are filled in with zeros.
    """
    year = year if year is not None else timezone.localdate().year
    start, end = year_bounds(year)
    rows = (
        WatchEntry.objects.for_user(user_id)
        .filter(watched_at__gte=start, watched_at__lt=end)
        .annotate(minutes=watch_minutes(), month=TruncMonth('watched_at'))
        .values('month')
        .annotate(
            movie_minutes=Coalesce(Sum('minutes', filter=MOVIE_ENTRY), 0),
            episode_minutes=Coalesce(Sum('minutes', filter=EPISODE_ENTRY), 0),
        )
    )
    by_month = {row['month'].month: row for row in rows}
    series = []
    for month in range(1, 13):
        row = by_month.get(month, {})
        series.append({
            'month': f'{year}-{month:02d}',
            'movie_minutes': row.get('movie_minutes', 0),
            'episode_minutes': row.get('episode_minutes', 0),
        })
    return {'year': year, 'months': series}
