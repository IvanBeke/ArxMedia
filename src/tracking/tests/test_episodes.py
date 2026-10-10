from datetime import UTC, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Episode, Season, TVShow
from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)
from tracking.status_sync import refresh_show_status

User = get_user_model()
from .base import BaseTestCase


class EpisodeTests(BaseTestCase):
    def test_mark_episode_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/mark/', data)
        self.assertEqual(response.status_code, 201)

    def test_unmark_episode_watched(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )
        data = {'tmdb_id': 123, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/episodes/unmark/', data)
        self.assertEqual(response.status_code, 200)

    def test_mark_episode_watched_allows_season_zero(self):
        response = self.client.post('/api/tracking/episodes/mark/', {
            'tmdb_id': 124,
            'season_number': 0,
            'episode_number': 1,
        })

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=124,
                season_number=0,
                episode_number=1,
            ).exists()
        )

    def test_unmark_episode_watched_allows_season_zero(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=124,
            season_number=0,
            episode_number=1,
        )

        response = self.client.post('/api/tracking/episodes/unmark/', {
            'tmdb_id': 124,
            'season_number': 0,
            'episode_number': 1,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['deleted'])

    def test_get_watched_episodes(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )
        response = self.client.get('/api/tracking/episodes/watched/?tmdb_id=123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['episodes']), 1)


class SeasonTests(BaseTestCase):
    def test_mark_season_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1}
        response = self.client.post('/api/tracking/seasons/mark/', data)
        self.assertEqual(response.status_code, 404)

    def test_unmark_season_watched(self):
        data = {'tmdb_id': 123, 'season_number': 1}
        response = self.client.post('/api/tracking/seasons/unmark/', data)
        self.assertEqual(response.status_code, 200)

    def test_mark_season_watched_returns_episode_records(self):
        show = TVShow.objects.create(tmdb_id=124, name='Season Show')
        season = Season.objects.create(show=show, tmdb_id=1241, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12411, episode_number=1, name='Episode 1')
        Episode.objects.create(season=season, tmdb_id=12412, episode_number=3, name='Episode 3')

        response = self.client.post('/api/tracking/seasons/mark/', {
            'tmdb_id': show.tmdb_id,
            'season_number': season.season_number,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marked'], 2)
        self.assertEqual(
            {(episode['season_number'], episode['episode_number']) for episode in response.data['episodes']},
            {(1, 1), (1, 3)},
        )
        self.assertTrue(all(episode['watched_at'] for episode in response.data['episodes']))

    def test_mark_season_watched_twice_does_not_duplicate_entries(self):
        show = TVShow.objects.create(tmdb_id=125, name='Twice Show')
        season = Season.objects.create(show=show, tmdb_id=1251, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=12511, episode_number=1, name='Episode 1')
        Episode.objects.create(season=season, tmdb_id=12512, episode_number=2, name='Episode 2')

        for _ in range(2):
            response = self.client.post('/api/tracking/seasons/mark/', {'tmdb_id': 125, 'season_number': 1})
            self.assertEqual(response.status_code, 200)

        self.assertEqual(WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=125).count(), 2)

    def test_mark_season_zero_watched(self):
        show = TVShow.objects.create(tmdb_id=126, name='Specials Show')
        season = Season.objects.create(show=show, tmdb_id=1260, season_number=0, name='Specials')
        Episode.objects.create(season=season, tmdb_id=12601, episode_number=1, name='Special 1')

        response = self.client.post('/api/tracking/seasons/mark/', {
            'tmdb_id': show.tmdb_id,
            'season_number': season.season_number,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marked'], 1)
        self.assertTrue(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=show.tmdb_id,
                season_number=0,
                episode_number=1,
            ).exists()
        )

    def test_unmark_season_watched_returns_deleted_episode_records(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=125,
            season_number=2,
            episode_number=4,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 1, 10, 0, 0)),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=125,
            season_number=2,
            episode_number=7,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 2, 10, 0, 0)),
        )

        response = self.client.post('/api/tracking/seasons/unmark/', {
            'tmdb_id': 125,
            'season_number': 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unmarked'], 2)
        self.assertEqual(
            {(episode['season_number'], episode['episode_number']) for episode in response.data['episodes']},
            {(2, 4), (2, 7)},
        )

    def test_unmark_show_watched(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=2
        )
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=456,
            season_number=1, episode_number=1
        )
        WatchEntry.objects.create(
            user=self.user2, media_type='episode', tmdb_id=123,
            season_number=1, episode_number=1
        )

        response = self.client.post('/api/tracking/shows/unmark/', {'tmdb_id': 123})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('unmarked'), 2)

        self.assertFalse(
            WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=123).exists()
        )
        self.assertTrue(
            WatchEntry.objects.filter(user=self.user, media_type='episode', tmdb_id=456).exists()
        )
        self.assertTrue(
            WatchEntry.objects.filter(user=self.user2, media_type='episode', tmdb_id=123).exists()
        )

    def test_mark_show_watched_marks_every_season_once(self):
        show = TVShow.objects.create(tmdb_id=330, name='Whole Show', number_of_seasons=2)
        for number in (0, 1, 2):
            season = Season.objects.create(show=show, tmdb_id=3300 + number, season_number=number, name=f'S{number}')
            for episode_number in (1, 2):
                Episode.objects.create(season=season, tmdb_id=33000 + number * 10 + episode_number, episode_number=episode_number, name='E')
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=330, season_number=1, episode_number=1)

        with patch('tracking.views.episodes.refresh_show_status', wraps=refresh_show_status) as refresh:
            response = self.client.post('/api/tracking/shows/mark/', {'tmdb_id': 330})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(
            {(row['season_number'], row['episode_number']) for row in response.data['episodes']},
            {(s, e) for s in (1, 2) for e in (1, 2)},
        )
        self.assertFalse(WatchEntry.objects.filter(user=self.user, tmdb_id=330, season_number=0).exists())

    def test_mark_show_and_season_use_each_episode_release_date(self):
        from datetime import date as date_cls

        show = TVShow.objects.create(tmdb_id=331, name='Release Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=3311, season_number=1, name='S1')
        Episode.objects.create(season=season, tmdb_id=33111, episode_number=1, name='E1', air_date=date_cls(2024, 1, 5))
        broadcast = datetime(2024, 1, 12, 21, 0, tzinfo=UTC)
        Episode.objects.create(
            season=season, tmdb_id=33112, episode_number=2, name='E2', air_date=date_cls(2024, 1, 12), broadcast_start=broadcast,
        )
        Episode.objects.create(season=season, tmdb_id=33113, episode_number=3, name='E3', air_date=None)

        for url, payload in (
            ('/api/tracking/shows/mark/', {'tmdb_id': 331}),
            ('/api/tracking/seasons/mark/', {'tmdb_id': 331, 'season_number': 1}),
        ):
            with self.subTest(url=url):
                WatchEntry.objects.filter(user=self.user, tmdb_id=331).delete()
                before = timezone.now()
                response = self.client.post(url, {**payload, 'watched_at': 'release_date'}, format='json')
                self.assertEqual(response.status_code, 200)
                watched = {e.episode_number: e.watched_at for e in WatchEntry.objects.filter(user=self.user, tmdb_id=331)}
                self.assertEqual(timezone.localtime(watched[1]).date(), date_cls(2024, 1, 5))
                self.assertEqual(watched[2], broadcast)
                self.assertGreaterEqual(watched[3], before)

    def test_mark_show_watched_validates_input(self):
        self.assertEqual(self.client.post('/api/tracking/shows/mark/', {}).status_code, 400)
        self.assertEqual(self.client.post('/api/tracking/shows/mark/', {'tmdb_id': 999999}).status_code, 404)

    def test_bulk_unmark_refreshes_show_status_once(self):
        show = TVShow.objects.create(tmdb_id=321, name='Bulk Show')
        season = Season.objects.create(show=show, tmdb_id=3211, season_number=1, name='Season 1')
        for number in range(1, 6):
            Episode.objects.create(season=season, tmdb_id=32110 + number, episode_number=number, name=f'E{number}')
            WatchEntry.objects.create(
                user=self.user, media_type='episode', tmdb_id=321, season_number=1, episode_number=number,
            )
        self.assertTrue(UserMediaStatus.objects.shows().filter(user=self.user, tmdb_id=321).exists())

        for url, payload in (
            ('/api/tracking/seasons/unmark/', {'tmdb_id': 321, 'season_number': 1}),
            ('/api/tracking/shows/unmark/', {'tmdb_id': 321}),
        ):
            with self.subTest(url=url), \
                    patch('tracking.views.episodes.refresh_show_status', wraps=refresh_show_status) as refresh, \
                    patch('tracking.signals.refresh_show_status') as per_row_refresh:
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(refresh.call_count, 1 if response.data['unmarked'] else 0)
                per_row_refresh.assert_not_called()
            WatchEntry.objects.bulk_create([
                WatchEntry(user=self.user, media_type='episode', tmdb_id=321, season_number=1, episode_number=n)
                for n in range(1, 6)
            ])

        self.client.post('/api/tracking/shows/unmark/', {'tmdb_id': 321})
        self.assertFalse(
            UserMediaStatus.objects.shows().filter(user=self.user, tmdb_id=321, status='watched').exists()
        )

    def test_mark_season_watched_invalidates_user_stats(self):
        show = TVShow.objects.create(tmdb_id=322, name='Stats Show')
        season = Season.objects.create(show=show, tmdb_id=3221, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=32211, episode_number=1, name='E1')

        with patch('tracking.views.episodes.cache.invalidate_user_stats') as invalidate:
            response = self.client.post('/api/tracking/seasons/mark/', {'tmdb_id': 322, 'season_number': 1})

        self.assertEqual(response.status_code, 200)
        invalidate.assert_called_once_with(self.user.id)

    def test_unmark_show_watched_requires_tmdb_id(self):
        response = self.client.post('/api/tracking/shows/unmark/', {})
        self.assertEqual(response.status_code, 400)
