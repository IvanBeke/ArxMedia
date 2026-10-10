
from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from media.models import Episode, Movie, Season, TVShow
from tracking.models import (
    CustomList,
    ListCollaborator,
    ListItem,
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()
from .base import BaseTestCase


class QueryCountTests(BaseTestCase):
    """List endpoints must cost a fixed number of queries however many rows they return."""

    def _add_rows(self, start, count):
        for i in range(start, start + count):
            show = TVShow.objects.create(tmdb_id=9100 + i, name=f'Show {i}', number_of_seasons=1)
            season = Season.objects.create(show=show, tmdb_id=9200 + i, season_number=1, name='Season 1')
            Episode.objects.create(season=season, tmdb_id=9300 + i, episode_number=1, name='Pilot')
            Movie.objects.create(tmdb_id=9400 + i, title=f'Movie {i}')
            WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=9100 + i, season_number=1, episode_number=1, watched_at=timezone.now())
            WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=9400 + i, watched_at=timezone.now())
            custom_list = CustomList.objects.create(user=self.user, name=f'List {i}')
            ListCollaborator.objects.create(custom_list=custom_list, user=self.user2)
            ListItem.objects.create(custom_list=custom_list, media_type='movie', tmdb_id=9400 + i)
            # Not stored locally: serializers must not query for media missing from the view's maps.
            UserMediaStatus.objects.set_planning(self.user, 'movie', 9500 + i)

    def _query_count(self, url):
        django_cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)

    def test_sorting_only_computes_the_requested_sort_field(self):
        UserMediaStatus.objects.set_planning(self.user, 'movie', 9600)

        def page_sql(sort):
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get('/api/tracking/watchlist/', {'sort': sort}).status_code, 200)
            return next(q['sql'] for q in ctx.captured_queries if 'ORDER BY' in q['sql'] and 'tracking_usermediastatus' in q['sql'])

        title_sql = page_sql('title')
        self.assertNotIn('vote_count', title_sql)
        self.assertNotIn('runtime', title_sql)
        self.assertIn('vote_count', page_sql('vote_count'))

    def _add_library_rows(self, start, count):
        for i in range(start, start + count):
            show = TVShow.objects.create(tmdb_id=9600 + i, name=f'Library Show {i}', number_of_seasons=1)
            season = Season.objects.create(show=show, tmdb_id=9700 + i, season_number=1, name='Season 1')
            Episode.objects.create(season=season, tmdb_id=9800 + i, episode_number=1, name='Pilot')
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=9600 + i,
                season_number=1, episode_number=1, watched_at=timezone.now(),
            )
            UserMediaStatus.objects.update_or_create(
                user=self.user, media_type='tv', tmdb_id=9600 + i, defaults={'status': 'watching'},
            )
            UserMediaStatus.objects.set_planning(self.user, 'movie', 9900 + i)

    def test_library_endpoints_do_not_query_per_row(self):
        urls = ['/api/tracking/my-shows/', '/api/tracking/my-movies/']
        self._add_library_rows(0, 2)
        before = {url: self._query_count(url) for url in urls}
        self._add_library_rows(2, 6)
        after = {url: self._query_count(url) for url in urls}

        self.assertEqual(after, before)

    def test_list_endpoints_do_not_query_per_row(self):
        urls = ['/api/tracking/stats/', '/api/tracking/history/', '/api/tracking/lists/', '/api/tracking/watchlist/']
        self._add_rows(0, 2)
        before = {url: self._query_count(url) for url in urls}
        self._add_rows(2, 6)
        after = {url: self._query_count(url) for url in urls}

        self.assertEqual(after, before)


class WatchEntryIndexTests(BaseTestCase):
    def _plan(self, queryset):
        sql, params = queryset.query.sql_with_params()
        with connection.cursor() as cursor:
            # Tiny test tables favour sequential scans; force the planner to show index usability.
            cursor.execute('SET LOCAL enable_seqscan = off')
            cursor.execute('SET LOCAL enable_bitmapscan = off')
            # Statistics left by other tests can make "other index + sort" look cheaper; forbid sorting so the
            # plan shows whether an index can serve the ordering on its own.
            cursor.execute('SET LOCAL enable_sort = off')
            cursor.execute('EXPLAIN ' + sql, params)
            return '\n'.join(row[0] for row in cursor.fetchall())

    def test_history_page_is_read_in_order_from_the_history_index(self):
        from tracking.views.history import WatchEntryListCreateView

        view = WatchEntryListCreateView()
        view.request = type('Request', (), {'user': self.user, 'query_params': {}})()
        plan = self._plan(view.get_queryset()[:20])

        self.assertIn('watchentry_user_history_idx', plan)
        self.assertNotIn('Sort', plan)

    def test_recent_activity_uses_the_user_watched_index(self):
        plan = self._plan(WatchEntry.objects.filter(user=self.user).order_by('-watched_at')[:10])

        self.assertIn('watchentry_user_watched_idx', plan)
        self.assertNotIn('Sort', plan)
