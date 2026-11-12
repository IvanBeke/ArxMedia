from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from media.tests.factories import EpisodeFactory, MovieFactory, SeasonFactory, TVShowFactory
from notifications.models import Notification
from notifications.tasks import generate_release_notifications
from tracking.tests.factories import UserMediaStatusFactory

pytestmark = pytest.mark.django_db


def track(user, item, *, status='plan_to_watch', media_type='movie'):
    return UserMediaStatusFactory(user=user, tmdb_id=item.tmdb_id, media_type=media_type, status=status)


def test_daily_movie_releases_and_current_recipients(user, user2):
    today = timezone.localdate()
    movie = MovieFactory(release_date=today)
    track(user, movie)
    track(user2, movie, status='watched')
    for day in (today - timedelta(days=1), today + timedelta(days=1), None):
        track(user, MovieFactory(release_date=day))
    track(user, MovieFactory(release_date=today), status='dropped')
    MovieFactory(release_date=today)

    generate_release_notifications()
    assert list(Notification.objects.values_list('user_id', 'tmdb_id', 'read', 'season_number')) == [
        (user.id, movie.tmdb_id, False, None),
    ]
    Notification.objects.update(read=True)
    generate_release_notifications()
    assert list(Notification.objects.values_list('read', flat=True)) == [True]


@pytest.mark.parametrize('season_number', [1, 2, 3])
@pytest.mark.parametrize('status', ['plan_to_watch', 'watching', 'watched', 'dropped'])
def test_tv_premiere_recipients(user, season_number, status):
    season = SeasonFactory(season_number=season_number)
    EpisodeFactory(season=season, episode_number=1, air_date=timezone.localdate())
    track(user, season.show, status=status, media_type='tv')

    generate_release_notifications()
    expected = status == 'plan_to_watch' if season_number == 1 else status != 'dropped'
    assert Notification.objects.count() == int(expected)
    if expected:
        assert Notification.objects.get().season_number == season_number


def test_excludes_specials_later_episodes_and_unknown_dates(user):
    show = TVShowFactory()
    track(user, show, media_type='tv')
    for season_number, episode_number, day in ((0, 1, timezone.localdate()), (1, 2, timezone.localdate()), (2, 1, None)):
        EpisodeFactory(
            season=SeasonFactory(show=show, season_number=season_number), episode_number=episode_number, air_date=day,
        )
    generate_release_notifications()
    assert not Notification.objects.exists()


def test_broadcast_local_day_takes_precedence_over_air_date(user, mocker):
    now = datetime(2026, 11, 12, 0, 5, tzinfo=ZoneInfo('Europe/Madrid'))
    mocker.patch('notifications.tasks.timezone.now', return_value=now)
    with timezone.override('Europe/Madrid'):
        season = SeasonFactory(season_number=2)
        track(user, season.show, media_type='tv', status='watching')
        episode = EpisodeFactory(
            season=season, episode_number=1, air_date=now.date() - timedelta(days=1),
            broadcast_start=datetime(2026, 11, 11, 23, 30, tzinfo=ZoneInfo('UTC')),
        )
        generate_release_notifications()
        assert Notification.objects.count() == 1
        Notification.objects.all().delete()
        # A future broadcast date overrides an air date of today.
        episode.broadcast_start = now + timedelta(days=1)
        episode.air_date = now.date()
        episode.save()
        generate_release_notifications()
        assert not Notification.objects.exists()


def test_each_season_is_distinct(user):
    show = TVShowFactory()
    track(user, show, media_type='tv')
    for number in (1, 2):
        EpisodeFactory(
            season=SeasonFactory(show=show, season_number=number), episode_number=1, air_date=timezone.localdate(),
        )
    generate_release_notifications()
    assert sorted(Notification.objects.values_list('season_number', flat=True)) == [1, 2]


def test_list_returns_only_own_notifications_newest_first(auth_client, user, user2):
    first = Notification.objects.create(user=user, media_type='movie', tmdb_id=1)
    second = Notification.objects.create(user=user, media_type='movie', tmdb_id=2)
    Notification.objects.create(user=user2, media_type='movie', tmdb_id=3)

    response = auth_client.get('/api/notifications/')
    assert response.status_code == 200
    assert response.data['count'] == 2
    assert [item['id'] for item in response.data['results']] == [second.id, first.id]


def test_list_includes_catalog_metadata(auth_client, user):
    movie = MovieFactory(title='Release movie', poster_path='/movie.jpg')
    show = TVShowFactory(name='Release show', poster_path='/show.jpg')
    Notification.objects.create(user=user, media_type='movie', tmdb_id=movie.tmdb_id)
    for number, poster in ((1, '/first.jpg'), (2, '')):
        SeasonFactory(show=show, season_number=number, poster_path=poster)
        Notification.objects.create(user=user, media_type='tv', tmdb_id=show.tmdb_id, season_number=number)

    results = {
        (item['media_type'], item['season_number']): item
        for item in auth_client.get('/api/notifications/').data['results']
    }
    assert results['movie', None]['title'] == movie.title
    assert results['tv', 1]['title'] == show.name
    assert results['movie', None]['poster_url'].endswith('/movie.jpg')
    assert results['tv', 1]['poster_url'].endswith('/first.jpg')
    assert results['tv', 2]['poster_url'].endswith('/show.jpg')
    assert all(item['release_date'] == timezone.localdate() for item in results.values())
    assert not any(item['read'] for item in results.values())


def test_list_query_count_does_not_grow_with_rows(auth_client, user):
    movie = MovieFactory(release_date=timezone.localdate())
    show = TVShowFactory()
    Notification.objects.create(user=user, media_type='movie', tmdb_id=movie.tmdb_id)
    Notification.objects.create(user=user, media_type='tv', tmdb_id=show.tmdb_id, season_number=2)

    def query_count():
        with CaptureQueriesContext(connection) as queries:
            assert auth_client.get('/api/notifications/').status_code == 200
        return len(queries)

    initial = query_count()
    for number in range(3, 11):
        Notification.objects.create(user=user, media_type='tv', tmdb_id=show.tmdb_id, season_number=number)
    assert query_count() == initial


def test_missing_catalog_metadata_is_safe(auth_client, user):
    Notification.objects.create(user=user, media_type='tv', tmdb_id=999, season_number=2)
    item = auth_client.get('/api/notifications/').data['results'][0]
    assert item['title'] == ''
    assert item['poster_url'] is None


def test_read_delete_and_unread_count(auth_client, user, user2):
    mine = Notification.objects.create(user=user, media_type='movie', tmdb_id=1)
    theirs = Notification.objects.create(user=user2, media_type='movie', tmdb_id=1)
    assert auth_client.get('/api/notifications/unread-count/').data == {'unread_count': 1}
    for _ in range(2):
        assert auth_client.post(f'/api/notifications/{mine.id}/read/').status_code == 204
    assert auth_client.get('/api/notifications/unread-count/').data == {'unread_count': 0}
    assert auth_client.post(f'/api/notifications/{theirs.id}/read/').status_code == 404
    assert auth_client.delete(f'/api/notifications/{theirs.id}/').status_code == 404
    assert auth_client.delete(f'/api/notifications/{mine.id}/').status_code == 204
    theirs.refresh_from_db()
    assert not theirs.read


@pytest.mark.parametrize(('method', 'path'), [
    ('get', ''), ('get', 'unread-count/'), ('post', '{id}/read/'), ('delete', '{id}/'),
])
def test_requires_authentication(api_client, user, method, path):
    item = Notification.objects.create(user=user, media_type='movie', tmdb_id=1)
    response = getattr(api_client, method)(f'/api/notifications/{path.format(id=item.id)}')
    assert response.status_code == 401
