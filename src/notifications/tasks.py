from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from media.models import Episode, Movie
from tracking.choices import TvShowStatus
from tracking.models import UserMediaStatus

from .models import Notification


def _create_notifications(statuses, *, season_number=None):
    Notification.objects.bulk_create(
        [
            Notification(user_id=user_id, tmdb_id=tmdb_id, media_type=media_type, season_number=season_number)
            for user_id, tmdb_id, media_type in statuses.values_list('user_id', 'tmdb_id', 'media_type')
        ],
        ignore_conflicts=True,
    )


@shared_task(name='notifications.generate_release_notifications')
def generate_release_notifications() -> dict[str, int | str]:
    """Announce today's releases only; intentionally no history or dispatch bookkeeping."""
    today = timezone.localdate()

    movie_ids = list(Movie.objects.filter(release_date=today).values_list('tmdb_id', flat=True))
    _create_notifications(UserMediaStatus.objects.movies().planning().filter(tmdb_id__in=movie_ids))

    premieres = list(
        Episode.objects.filter(Episode.regular_q(), episode_number=1).filter(
            Q(broadcast_start__date=today) | Q(broadcast_start__isnull=True, air_date=today),
        ).values_list('season__show__tmdb_id', 'season__season_number')
    )
    for tmdb_id, season_number in premieres:
        statuses = UserMediaStatus.objects.shows().filter(tmdb_id=tmdb_id)
        recipients = statuses.planning() if season_number == 1 else statuses.exclude(status=TvShowStatus.DROPPED)
        _create_notifications(recipients, season_number=season_number)

    return {'date': today.isoformat(), 'movies': len(movie_ids), 'seasons': len(premieres)}
