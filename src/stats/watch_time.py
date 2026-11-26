from django.db.models import Sum
from django.db.models.functions import Coalesce

from tracking.models import WatchEntry

from .entries import EPISODE_ENTRY, MOVIE_ENTRY, watch_minutes


def watch_time_stats(user_id):
    """Runtime of the movies and episodes the user has watched, in minutes, in a single query.

    Entries with no known runtime (or whose media is not synced locally) contribute 0 minutes.
    """
    row = (
        WatchEntry.objects.for_user(user_id)
        .annotate(minutes=watch_minutes())
        .aggregate(
            movie_minutes=Coalesce(Sum('minutes', filter=MOVIE_ENTRY), 0),
            episode_minutes=Coalesce(Sum('minutes', filter=EPISODE_ENTRY), 0),
        )
    )
    return {**row, 'watch_time_minutes': row['movie_minutes'] + row['episode_minutes']}
