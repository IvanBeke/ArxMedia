from django.db.models import Count, Q

from tracking.choices import MOVIE_STATUSES, MediaType, TvShowStatus
from tracking.models import UserMediaStatus


def library_stats(user_id):
    """What the user tracks: counts per status for shows and movies, per media type, and the watchlist size.

    Everything is counted by a single query.
    """
    row = UserMediaStatus.objects.for_user(user_id).aggregate(
        shows=Count('id', filter=Q(media_type=MediaType.TV)),
        movies=Count('id', filter=Q(media_type=MediaType.MOVIE)),
        watchlist_count=Count('id', filter=Q(status=TvShowStatus.PLAN_TO_WATCH)),
        **{
            f'show_{status}': Count('id', filter=Q(media_type=MediaType.TV, status=status))
            for status in TvShowStatus.values
        },
        **{
            f'movie_{status}': Count('id', filter=Q(media_type=MediaType.MOVIE, status=status))
            for status in MOVIE_STATUSES
        },
    )
    return {
        'show_statuses': {status: row[f'show_{status}'] for status in TvShowStatus.values},
        'movie_statuses': {status: row[f'movie_{status}'] for status in MOVIE_STATUSES},
        'media_types': {MediaType.MOVIE: row['movies'], MediaType.TV: row['shows']},
        'watchlist_count': row['watchlist_count'],
    }
