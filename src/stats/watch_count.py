from django.db.models import Count

from tracking.models import WatchEntry

from .entries import EPISODE_ENTRY, MOVIE_ENTRY


def watch_count_stats(user_id):
    """How many movies and episodes the user has watched, in a single query."""
    return WatchEntry.objects.for_user(user_id).aggregate(
        movies_watched=Count('id', filter=MOVIE_ENTRY),
        episodes_watched=Count('id', filter=EPISODE_ENTRY),
    )
