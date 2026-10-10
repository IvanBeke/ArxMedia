from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from media.models import Episode, Season, TVShow
from tracking.choices import MediaType, WatchEntryMediaType
from tracking.models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)
from tracking.status_sync import rebuild_episode_chain, refresh_show_status

User = get_user_model()
from .base import BaseTestCase


class WatchEntryTests(BaseTestCase):
    def test_watch_entry_and_status_queryset_helpers(self):
        show_one = TVShow.objects.create(tmdb_id=1, name='Show One')
        show_two = TVShow.objects.create(tmdb_id=2, name='Show Two')
        season_one = Season.objects.create(show=show_one, tmdb_id=101, season_number=1, name='Season 1')
        season_two = Season.objects.create(show=show_two, tmdb_id=102, season_number=1, name='Season 1')
        Episode.objects.create(season=season_one, tmdb_id=1001, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1))
        Episode.objects.create(season=season_two, tmdb_id=1002, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1))
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=1, status='watching', watched_episodes=1)
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=2, status='watched', watched_episodes=2)
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=3, status='dropped', watched_episodes=1)
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=4, status='plan_to_watch')
        WatchEntry.objects.create(user=self.user, media_type=WatchEntryMediaType.EPISODE, tmdb_id=1, season_number=1, episode_number=1)
        WatchEntry.objects.create(user=self.user, media_type=WatchEntryMediaType.EPISODE, tmdb_id=2, season_number=1, episode_number=1)
        WatchEntry.objects.create(user=self.user, media_type=WatchEntryMediaType.MOVIE, tmdb_id=10)
        WatchEntry.objects.create(user=self.user, media_type=WatchEntryMediaType.EPISODE, tmdb_id=11, season_number=1, episode_number=1)

        statuses = UserMediaStatus.objects.for_user(self.user).filter(tmdb_id__in=[1, 2, 3, 4])
        self.assertEqual(statuses.started().count(), 3)
        self.assertEqual(statuses.active().count(), 2)
        self.assertEqual(statuses.progressable().count(), 2)
        self.assertEqual(WatchEntry.objects.for_user(self.user).movies().count(), 1)
        self.assertEqual(WatchEntry.objects.for_user(self.user).episodes().for_show(11).count(), 1)

    def test_episode_chain_and_released_remaining_status(self):
        show = TVShow.objects.create(tmdb_id=8800, name='Linked Show')
        season_one = Season.objects.create(show=show, tmdb_id=8801, season_number=1, name='Season 1')
        season_two = Season.objects.create(show=show, tmdb_id=8802, season_number=2, name='Season 2')
        yesterday = timezone.localdate() - timedelta(days=1)
        tomorrow = timezone.localdate() + timedelta(days=1)
        first = Episode.objects.create(season=season_one, tmdb_id=8810, episode_number=1, name='One', air_date=yesterday, runtime=40)
        second = Episode.objects.create(season=season_one, tmdb_id=8811, episode_number=2, name='Two', air_date=yesterday, runtime=None)
        third = Episode.objects.create(season=season_two, tmdb_id=8820, episode_number=1, name='Three', air_date=tomorrow, runtime=50)

        rebuild_episode_chain(show.tmdb_id)
        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(first.next_episode_id, second.id)
        self.assertEqual(second.next_episode_id, third.id)
        self.assertIsNone(third.next_episode_id)

        WatchEntry.objects.create(
            user=self.user, media_type=WatchEntryMediaType.EPISODE, tmdb_id=show.tmdb_id,
            season_number=1, episode_number=1,
        )
        status_row = UserMediaStatus.objects.get(user=self.user, media_type=MediaType.TV, tmdb_id=show.tmdb_id)
        self.assertEqual(status_row.total_episodes, 2)
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(status_row.episodes_left, 1)
        self.assertEqual(status_row.time_left_minutes, 0)
        self.assertTrue(status_row.time_left_has_unknown)

    def test_create_movie_watched(self):
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WatchEntry.objects.count(), 1)

    def test_create_episode_watched(self):
        data = {'media_type': 'episode', 'tmdb_id': 456, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)

    def test_create_show_watching_rejected(self):
        data = {'media_type': 'show', 'tmdb_id': 789, 'status': 'watching'}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 400)

    def test_remove_from_watchlist_on_watch(self):
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=999, status='plan_to_watch', status_changed_at=timezone.now())
        self.assertEqual(UserMediaStatus.objects.planning().count(), 1)
        data = {'media_type': 'movie', 'tmdb_id': 999}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserMediaStatus.objects.planning().count(), 0)

    def test_episode_watch_moves_planned_show_to_watching(self):
        from media.models import Episode, Season, TVShow

        show = TVShow.objects.create(tmdb_id=888, name='Planned Show', number_of_seasons=1)
        season = Season.objects.create(show=show, tmdb_id=889, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=890, episode_number=1, name='Pilot', air_date=timezone.localdate() - timedelta(days=1))
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=888, status='plan_to_watch', status_changed_at=timezone.now())
        self.assertEqual(UserMediaStatus.objects.planning().count(), 1)

        data = {'media_type': 'episode', 'tmdb_id': 888, 'season_number': 1, 'episode_number': 1}
        response = self.client.post('/api/tracking/history/', data)
        self.assertEqual(response.status_code, 201)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=888)
        self.assertEqual(status_row.status, 'watching')
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(UserMediaStatus.objects.planning().count(), 0)

    def test_show_progress_uses_released_episodes_and_floors_percentage(self):
        show = TVShow.objects.create(tmdb_id=889, name='Released Progress Show')
        season = Season.objects.create(show=show, tmdb_id=890, season_number=1, name='Season 1')
        yesterday = timezone.now().date() - timedelta(days=1)
        tomorrow = timezone.now().date() + timedelta(days=1)
        for episode_number, air_date in ((1, yesterday), (2, yesterday), (3, yesterday), (4, tomorrow), (5, None)):
            Episode.objects.create(
                season=season,
                tmdb_id=8900 + episode_number,
                episode_number=episode_number,
                name=f'Episode {episode_number}',
                air_date=air_date,
            )

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=show.tmdb_id,
            season_number=1,
            episode_number=1,
        )

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=show.tmdb_id)
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(status_row.total_episodes, 3)
        self.assertEqual(status_row.progress_percent, 33)

    def test_show_progress_ignores_orphan_watch_keys(self):
        show = TVShow.objects.create(tmdb_id=890, name='Orphan Progress Show', status='Ended')
        season = Season.objects.create(show=show, tmdb_id=891, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=892, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1), runtime=42)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=890, season_number=1, episode_number=1)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=890, season_number=1, episode_number=99)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=890)
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(status_row.total_episodes, 1)
        self.assertEqual(status_row.episodes_left, 0)
        self.assertEqual(status_row.time_left_minutes, 0)

    def test_show_progress_ignores_unreleased_watch_keys(self):
        show = TVShow.objects.create(tmdb_id=891, name='Future Progress Show', status='Returning Series')
        season = Season.objects.create(show=show, tmdb_id=892, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=893, episode_number=1, name='Released', air_date=timezone.localdate() - timedelta(days=1))
        Episode.objects.create(season=season, tmdb_id=894, episode_number=2, name='Future', air_date=timezone.localdate() + timedelta(days=1))
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=891, season_number=1, episode_number=2)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=891)
        self.assertEqual(status_row.watched_episodes, 0)
        self.assertEqual(status_row.total_episodes, 1)
        self.assertEqual(status_row.progress_percent, 0)
        self.assertEqual(status_row.episodes_left, 1)

    def test_reconcile_tv_progress_repairs_orphan_watch_key(self):
        show = TVShow.objects.create(tmdb_id=892, name='Repair Show', status='Ended')
        season = Season.objects.create(show=show, tmdb_id=893, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=894, episode_number=1, name='Episode 1', air_date=timezone.localdate() - timedelta(days=1), runtime=45)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=892, season_number=1, episode_number=1)
        WatchEntry.objects.create(user=self.user, media_type='episode', tmdb_id=892, season_number=1, episode_number=99)
        UserMediaStatus.objects.filter(user=self.user, media_type='tv', tmdb_id=892).update(
            watched_episodes=2, total_episodes=1, progress_percent=100, episodes_left=1, time_left_minutes=45,
        )

        refresh_show_status(self.user.id, 892)

        status_row = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=892)
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(status_row.total_episodes, 1)
        self.assertEqual(status_row.episodes_left, 0)
        self.assertEqual(status_row.time_left_minutes, 0)

        refresh_show_status(self.user.id, 892)
        status_row.refresh_from_db()
        self.assertEqual(status_row.watched_episodes, 1)
        self.assertEqual(status_row.episodes_left, 0)

    def test_drop_media_tv(self):
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=789,
            season_number=1, episode_number=1
        )
        response = self.client.post('/api/tracking/media/drop/', {'tmdb_id': 789, 'media_type': 'tv'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['dropped'])
        self.assertEqual(
            WatchEntry.objects.filter(
                user=self.user,
                media_type='episode',
                tmdb_id=789,
                season_number=1,
                episode_number=1,
            ).count(),
            1,
        )
        dropped_status = UserMediaStatus.objects.get(user=self.user, media_type='tv', tmdb_id=789)
        self.assertEqual(dropped_status.status, 'dropped')
        self.assertIsNotNone(dropped_status.dropped_at)

    def test_drop_media_movie(self):
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=555, status='plan_to_watch', status_changed_at=timezone.now())
        response = self.client.post('/api/tracking/media/drop/', {'tmdb_id': 555, 'media_type': 'movie'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['dropped'])
        dropped_status = UserMediaStatus.objects.get(user=self.user, media_type='movie', tmdb_id=555)
        self.assertEqual(dropped_status.status, 'dropped')
        self.assertIsNotNone(dropped_status.dropped_at)
        self.assertEqual(UserMediaStatus.objects.planning().count(), 0)

    def test_drop_media_requires_tmdb_id(self):
        response = self.client.post('/api/tracking/media/drop/', {'media_type': 'movie'})
        self.assertEqual(response.status_code, 400)

    def test_drop_media_requires_media_type(self):
        response = self.client.post('/api/tracking/media/drop/', {'tmdb_id': 999})
        self.assertEqual(response.status_code, 400)

    def test_drop_media_rejects_invalid_media_type(self):
        response = self.client.post('/api/tracking/media/drop/', {'tmdb_id': 999, 'media_type': 'book'})
        self.assertEqual(response.status_code, 400)

    def test_drop_media_not_found(self):
        response = self.client.post('/api/tracking/media/drop/', {'tmdb_id': 999, 'media_type': 'tv'})
        self.assertEqual(response.status_code, 200)

    def test_history_list_orders_by_watched_at_newest_first(self):
        older = timezone.make_aware(timezone.datetime(2026, 1, 1, 10, 0, 0))
        newer = timezone.make_aware(timezone.datetime(2026, 1, 2, 10, 0, 0))

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=500,
            season_number=1,
            episode_number=1,
            watched_at=older,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=600,
            watched_at=newer,
        )

        response = self.client.get('/api/tracking/history/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 600)

    def test_history_episode_payload_includes_show_and_episode_type_fields(self):
        show = TVShow.objects.create(tmdb_id=5001, name='Runtime Show', episode_runtime=41)
        season = Season.objects.create(
            show=show,
            tmdb_id=50010,
            season_number=1,
            name='Season 1',
        )
        Episode.objects.create(
            season=season,
            tmdb_id=500101,
            episode_number=1,
            name='Pilot',
            runtime=44,
            episode_type='season finale',
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=5001,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        entries = response.data.get('results', response.data)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['show_name'], 'Runtime Show')
        self.assertEqual(entries[0]['episode_type'], 'season finale')

    def test_history_list_filters_media_type(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=700,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=701,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/?media_type=movie')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['media_type'], 'movie')
        self.assertEqual(data[0]['tmdb_id'], 701)

    def test_history_list_filters_item_scope(self):
        matching = WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=702,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=702,
            season_number=1,
            episode_number=2,
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=702,
            season_number=2,
            episode_number=1,
            watched_at=timezone.now(),
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=702,
            watched_at=timezone.now(),
        )

        response = self.client.get(
            '/api/tracking/history/',
            {
                'media_type': 'episode',
                'tmdb_id': 702,
                'season_number': 1,
                'episode_number': 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual([entry['id'] for entry in data], [matching.id])

    def test_history_list_oldest_order(self):
        older = timezone.make_aware(timezone.datetime(2026, 2, 1, 10, 0, 0))
        newer = timezone.make_aware(timezone.datetime(2026, 2, 3, 10, 0, 0))

        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=800,
            watched_at=newer,
        )
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=801,
            watched_at=older,
        )

        response = self.client.get('/api/tracking/history/?order=oldest')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['tmdb_id'], 801)
        self.assertEqual(data[1]['tmdb_id'], 800)

    def test_history_episode_uses_episode_title_and_show_name(self):
        show = TVShow.objects.create(tmdb_id=1900, name='The Example Show')
        season = Season.objects.create(show=show, tmdb_id=2901, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=3901, episode_number=3, name='Pilot Episode')

        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=1900,
            season_number=1,
            episode_number=3,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['title'], 'Pilot Episode')
        self.assertEqual(data[0]['show_name'], 'The Example Show')

    def test_history_movie_includes_user_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=2101,
            watched_at=timezone.now(),
        )
        Rating.objects.create(
            user=self.user,
            media_type='movie',
            tmdb_id=2101,
            score=9,
        )

        response = self.client.get('/api/tracking/history/?media_type=movie')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['tmdb_id'], 2101)
        self.assertEqual(data[0]['rating'], 9)

    def test_history_episode_includes_show_rating(self):
        WatchEntry.objects.create(
            user=self.user,
            media_type='episode',
            tmdb_id=2102,
            season_number=1,
            episode_number=1,
            watched_at=timezone.now(),
        )
        Rating.objects.create(
            user=self.user,
            media_type='tv',
            tmdb_id=2102,
            score=8,
        )

        response = self.client.get('/api/tracking/history/?media_type=episode')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data)
        self.assertEqual(data[0]['tmdb_id'], 2102)
        self.assertEqual(data[0]['rating'], 8)


class HistoryCreateIdempotencyTests(BaseTestCase):
    def test_reposting_a_watched_movie_or_episode_returns_existing_entry(self):
        payloads = [
            {'media_type': 'movie', 'tmdb_id': 77},
            {'media_type': 'episode', 'tmdb_id': 78, 'season_number': 1, 'episode_number': 2},
        ]
        for payload in payloads:
            with self.subTest(media_type=payload['media_type']):
                first = self.client.post('/api/tracking/history/', payload, format='json')
                second = self.client.post('/api/tracking/history/', payload, format='json')

                self.assertEqual(first.status_code, 201)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(second.data['id'], first.data['id'])
                self.assertEqual(
                    WatchEntry.objects.filter(user=self.user, media_type=payload['media_type'], tmdb_id=payload['tmdb_id']).count(),
                    1,
                )


class SpecialEpisodeHistoryTests(BaseTestCase):
    """Season 0 (specials) must resolve titles, shows and posters like any other season."""

    def test_history_resolves_special_episode_details(self):
        show = TVShow.objects.create(tmdb_id=700, name='Special Show')
        season = Season.objects.create(show=show, tmdb_id=7000, season_number=0, name='Specials', poster_path='/s0.jpg')
        Episode.objects.create(season=season, tmdb_id=70001, episode_number=1, name='Special One')
        WatchEntry.objects.create(
            user=self.user, media_type='episode', tmdb_id=700, season_number=0, episode_number=1,
            watched_at=timezone.now(),
        )

        response = self.client.get('/api/tracking/history/', {'tmdb_id': 700, 'media_type': 'episode'})

        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['title'], 'Special One')
        self.assertEqual(row['show_name'], 'Special Show')
        self.assertTrue(row['poster_url'].endswith('/s0.jpg'))
