
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from media.models import Episode, Season, TVShow
from tracking.models import (
    Rating,
    UserMediaStatus,
    WatchEntry,
)
from tracking.status_annotations import annotate_season_user_status
from tracking.status_sync import refresh_all_statuses_for_show, refresh_show_status

User = get_user_model()


pytestmark = pytest.mark.django_db

class StatusAnnotationTests:
    def test_movie_rating_reported_only_with_non_planning_status(self, user, user2, tmdb_noop):
        from tracking.status_annotations import annotate_media_user_status

        UserMediaStatus.objects.set_planning(user, 'movie', 800)
        Rating.objects.create(user=user, media_type='movie', tmdb_id=800, score=7)

        planned = annotate_media_user_status(user, [{'media_type': 'movie', 'tmdb_id': 800}])
        assert planned[('movie', 800)]['status'] == 'plan_to_watch'
        assert planned[('movie', 800)]['rating'] is None

        UserMediaStatus.objects.filter(user=user, media_type='movie', tmdb_id=800).update(status='dropped')
        dropped = annotate_media_user_status(user, [{'media_type': 'movie', 'tmdb_id': 800}])
        assert dropped[('movie', 800)]['rating'] == 7

    def test_movie_rating_hidden_without_status_row(self, user, user2, tmdb_noop):
        from tracking.status_annotations import annotate_media_user_status

        Rating.objects.create(user=user, media_type='movie', tmdb_id=801, score=6)

        result = annotate_media_user_status(user, [{'media_type': 'movie', 'tmdb_id': 801}])

        assert result[('movie', 801)]['status'] is None
        assert result[('movie', 801)]['rating'] is None


class MaterializedStatusTests:
    def test_dropped_show_moves_to_watching_when_new_episode_is_watched(self, user, auth_client, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=9100, name='Resume Show', status='Ended')
        season = Season.objects.create(show=show, tmdb_id=91001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=910011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=910012, episode_number=2, name='Ep 2', air_date='2024-01-02')
        Episode.objects.create(season=season, tmdb_id=910013, episode_number=3, name='Ep 3', air_date='2024-01-03')

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9100,
            season_number=1,
            episode_number=1,
            watched_at=timezone.make_aware(timezone.datetime(2026, 1, 1, 10, 0, 0)),
        )
        auth_client.post('/api/tracking/media/drop/', {'tmdb_id': 9100, 'media_type': 'tv'})
        auth_client.post('/api/tracking/episodes/mark/', {'tmdb_id': 9100, 'season_number': 1, 'episode_number': 2})

        show_status = UserMediaStatus.objects.get(user=user, media_type='tv', tmdb_id=9100)
        assert show_status.status == 'watching'

    def test_non_final_tmdb_show_never_becomes_watched(self, user, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=9200, name='Ongoing Show', status='Returning Series')
        season = Season.objects.create(show=show, tmdb_id=92001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=920011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=920012, episode_number=2, name='Ep 2', air_date='2024-01-02')

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9200,
            season_number=1,
            episode_number=1,
        )
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9200,
            season_number=1,
            episode_number=2,
        )

        show_status = UserMediaStatus.objects.get(user=user, media_type='tv', tmdb_id=9200)
        season_status = annotate_season_user_status(
            user,
            [{'tmdb_id': 9200, 'season_number': 1}],
        )[(9200, 1)]
        assert show_status.status == 'watching'
        assert season_status['status'] == 'watching'

    def test_final_tmdb_show_becomes_watched_when_complete(self, user, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=9300, name='Finished Show', status='Canceled')
        season = Season.objects.create(show=show, tmdb_id=93001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=930011, episode_number=1, name='Ep 1', air_date='2024-01-01')
        Episode.objects.create(season=season, tmdb_id=930012, episode_number=2, name='Ep 2', air_date='2024-01-02')

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9300,
            season_number=1,
            episode_number=1,
        )
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9300,
            season_number=1,
            episode_number=2,
        )

        show_status = UserMediaStatus.objects.get(user=user, media_type='tv', tmdb_id=9300)
        season_status = annotate_season_user_status(
            user,
            [{'tmdb_id': 9300, 'season_number': 1}],
        )[(9300, 1)]
        assert show_status.status == 'watched'
        assert season_status['status'] == 'watched'

    def test_refresh_show_status_deletes_row_when_status_would_be_none(self, user, user2, tmdb_noop):
        TVShow.objects.create(tmdb_id=9400, name='No Signal Show', status='Ended')
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=9400, status='watching')

        refresh_show_status(user.id, 9400)

        assert not UserMediaStatus.objects.filter(user=user, media_type='tv', tmdb_id=9400).exists()

    def test_refresh_show_status_keeps_plan_to_watch_row(self, user, user2, tmdb_noop):
        TVShow.objects.create(tmdb_id=9401, name='Watchlist Only Show', status='Ended')
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=9401, status='plan_to_watch', status_changed_at=timezone.now())

        refresh_show_status(user.id, 9401)

        assert UserMediaStatus.objects.filter(user=user, media_type='tv', tmdb_id=9401, status='plan_to_watch').exists()

    def test_refresh_show_status_clears_stale_timestamps_for_plan_to_watch(self, user, user2, tmdb_noop):
        TVShow.objects.create(tmdb_id=9402, name='Stale Timestamp Show', status='Ended')
        UserMediaStatus.objects.create(
            user=user,
            media_type='tv',
            tmdb_id=9402,
            status='plan_to_watch',
            status_changed_at=timezone.now(),
            started_at=timezone.now(),
            last_watched_at=timezone.now(),
            watched_episodes=3,
            total_episodes=5,
        )

        refresh_show_status(user.id, 9402)

        row = UserMediaStatus.objects.get(user=user, media_type='tv', tmdb_id=9402)
        assert row.status == 'plan_to_watch'
        assert row.started_at is None
        assert row.last_watched_at is None
        assert row.completed_at is None
        assert row.watched_episodes == 0
        assert row.total_episodes == 0


class RefreshAllShowStatusesTests:
    def test_refreshes_current_user_sync_and_queues_remaining(self, mocker, user, user2, tmdb_noop):
        mock_refresh_show_status = mocker.patch('tracking.status_sync.refresh_show_status')
        mock_delay = mocker.patch('tracking.tasks.system.refresh_show_status_for_user.delay')
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=7770,
            season_number=1,
            episode_number=1,
        )
        UserMediaStatus.objects.create(user=user2, media_type='tv', tmdb_id=7770, status='watching')

        with TestCase.captureOnCommitCallbacks(execute=True):
            refresh_all_statuses_for_show(7770, current_user_id=user.id)

        mock_refresh_show_status.assert_called_once_with(user.id, 7770)
        mock_delay.assert_called_once_with(7770, user2.id)

    def test_no_logged_user_queues_all_candidates(self, mocker, user, user2, tmdb_noop):
        mock_refresh_show_status = mocker.patch('tracking.status_sync.refresh_show_status')
        mock_delay = mocker.patch('tracking.tasks.system.refresh_show_status_for_user.delay')
        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=7771,
            season_number=1,
            episode_number=1,
        )
        UserMediaStatus.objects.create(user=user2, media_type='tv', tmdb_id=7771, status='watching')

        with TestCase.captureOnCommitCallbacks(execute=True):
            refresh_all_statuses_for_show(7771)

        mock_refresh_show_status.assert_not_called()
        assert mock_delay.call_count == 2
        assert {tuple(call.args) for call in mock_delay.call_args_list} == {(7771, user.id), (7771, user2.id)}

    def test_watchlist_only_users_are_not_refreshed(self, mocker, user, user2, tmdb_noop):
        mock_refresh_show_status = mocker.patch('tracking.status_sync.refresh_show_status')
        mock_delay = mocker.patch('tracking.tasks.system.refresh_show_status_for_user.delay')
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=7772, status='plan_to_watch', status_changed_at=timezone.now())

        with TestCase.captureOnCommitCallbacks(execute=True):
            refresh_all_statuses_for_show(7772, current_user_id=user.id)

        mock_refresh_show_status.assert_called_once_with(user.id, 7772)
        mock_delay.assert_not_called()
