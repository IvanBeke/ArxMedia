from functools import partial

import pytest
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from stats.habits import habits_stats
from stats.library import library_stats
from stats.monthly import monthly_stats
from stats.ratings import rating_stats
from stats.watch_count import watch_count_stats
from stats.watch_time import watch_time_stats
from stats.years import years_stats
from tracking.models import Rating, UserMediaStatus, WatchEntry

pytestmark = pytest.mark.django_db


class StatsQueryCountTests:
    """Every figure is computed by the database: a fixed number of queries however much data there is."""

    def _add_rows(self, start, count, user):
        for i in range(start, start + count):
            show = TVShow.objects.create(tmdb_id=9100 + i, name=f'Show {i}', number_of_seasons=1, episode_runtime=30)
            season = Season.objects.create(show=show, tmdb_id=9200 + i, season_number=1, name='Season 1')
            Episode.objects.create(season=season, tmdb_id=9300 + i, episode_number=1, name='Pilot')
            Movie.objects.create(tmdb_id=9400 + i, title=f'Movie {i}', runtime=90)
            WatchEntry.objects.create(
                user=user, media_type='episode', tmdb_id=9100 + i, season_number=1, episode_number=1,
                watched_at=timezone.now(),
            )
            WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=9400 + i, watched_at=timezone.now())
            Rating.objects.create(user=user, media_type='movie', tmdb_id=9400 + i, score=i % 10 + 1)
            UserMediaStatus.objects.set_planning(user, 'movie', 9500 + i)

    @pytest.mark.parametrize(('compute', 'queries'), [
        (rating_stats, 1),
        (library_stats, 1),
        (watch_count_stats, 1),
        (watch_time_stats, 1),
        (monthly_stats, 1),
        (partial(monthly_stats, year=2025), 1),
        (years_stats, 1),
        (habits_stats, 2),
    ])
    def test_query_count_is_fixed(self, compute, queries, user, tmdb_noop, django_assert_num_queries):
        with django_assert_num_queries(queries):
            compute(user.id)

        self._add_rows(0, 8, user)

        with django_assert_num_queries(queries):
            compute(user.id)
