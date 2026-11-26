"""Watch-entry building blocks shared by the stats queries."""

from datetime import datetime

from django.db.models import Case, IntegerField, OuterRef, Q, Subquery, When
from django.utils import timezone

from tracking.choices import WatchEntryMediaType

MOVIE_ENTRY = Q(media_type=WatchEntryMediaType.MOVIE)
EPISODE_ENTRY = Q(media_type=WatchEntryMediaType.EPISODE)


def _movie_runtime():
    from media.models import Movie

    return Subquery(Movie.objects.filter(tmdb_id=OuterRef('tmdb_id')).values('runtime')[:1])


def _episode_runtime():
    from media.models import Episode

    return Subquery(
        Episode.objects.filter(
            season__show__tmdb_id=OuterRef('tmdb_id'),
            season__season_number=OuterRef('season_number'),
            episode_number=OuterRef('episode_number'),
        )
        .annotate(runtime_minutes=Episode.effective_runtime_expression())
        .values('runtime_minutes')[:1]
    )


def watch_minutes():
    """Runtime of a watch entry in minutes: the movie's, or the episode's with the show's default as fallback.

    Entries whose media is not synced locally, or has no known runtime, resolve to NULL.
    """
    return Case(
        When(MOVIE_ENTRY, then=_movie_runtime()),
        default=_episode_runtime(),
        output_field=IntegerField(),
    )


MIN_YEAR = 1900
MAX_YEAR = 2999


def year_bounds(year):
    """The first moment of `year` and of the next one, in the server timezone: entries of the year are `start <= watched_at < end`."""
    return timezone.make_aware(datetime(year, 1, 1)), timezone.make_aware(datetime(year + 1, 1, 1))
