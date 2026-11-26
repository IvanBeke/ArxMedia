from django.db.models import Count
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay

from tracking.choices import WatchEntryMediaType
from tracking.models import WatchEntry

from .entries import EPISODE_ENTRY, MOVIE_ENTRY

WEEKDAYS = 7
HOURS = 24


def _counts_by(entries, bucket, size, first_bucket):
    """Movies and episodes per bucket, counted by one query; buckets without entries stay at zero."""
    rows = (
        entries.annotate(bucket=bucket)
        .values('bucket')
        .annotate(movie=Count('id', filter=MOVIE_ENTRY), episode=Count('id', filter=EPISODE_ENTRY))
    )
    counts = {media_type: [0] * size for media_type in WatchEntryMediaType.values}
    for row in rows:
        counts[WatchEntryMediaType.MOVIE][row['bucket'] - first_bucket] = row['movie']
        counts[WatchEntryMediaType.EPISODE][row['bucket'] - first_bucket] = row['episode']
    return counts


def habits_stats(user_id):
    """When the user watches: counts by ISO weekday (Monday first) and by hour of day, per media type.

    Uses the server timezone and leaves out entries with an unknown watch date. Two queries.
    """
    entries = WatchEntry.objects.for_user(user_id).filter(watched_at__isnull=False)
    weekdays = _counts_by(entries, ExtractIsoWeekDay('watched_at'), WEEKDAYS, 1)
    hours = _counts_by(entries, ExtractHour('watched_at'), HOURS, 0)
    return {
        media_type: {'weekdays': weekdays[media_type], 'hours': hours[media_type]}
        for media_type in WatchEntryMediaType.values
    }
