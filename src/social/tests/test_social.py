import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.tests.factories import UserFactory
from media.tests.factories import EpisodeFactory, SeasonFactory, TVShowFactory
from social.tests.factories import FollowFactory
from tracking.models import Review, WatchEntry
from tracking.tests.factories import EpisodeWatchEntryFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def privacy_graph(db):
    viewer = UserFactory(username='viewer')
    public = UserFactory(username='public', account_visibility='public')
    private = UserFactory(username='private', account_visibility='private')
    friend = UserFactory(username='friend', account_visibility='friends_only')
    one_way = UserFactory(username='oneway', account_visibility='friends_only')
    for target in (public, private, friend, one_way):
        FollowFactory(follower=viewer, following=target)
    FollowFactory(follower=friend, following=viewer)
    return {'viewer': viewer, 'public': public, 'private': private, 'friend': friend, 'one_way': one_way}


def _authors(response):
    return {row['username'] for row in response.data}


class TestPrivacyFiltering:
    def test_feed_hides_followed_accounts_the_viewer_cannot_see(self, api_client, privacy_graph):
        api_client.force_authenticate(user=privacy_graph['viewer'])
        for index, key in enumerate(('public', 'private', 'friend', 'one_way')):
            WatchEntry.objects.create(
                user=privacy_graph[key], media_type='movie', tmdb_id=100 + index, watched_at=timezone.now()
            )

        response = api_client.get('/api/social/feed/')

        assert response.status_code == 200
        assert _authors(response) == {'public', 'friend'}

    def test_feed_requires_auth(self, api_client):
        assert api_client.get('/api/social/feed/').status_code == 401

    def test_reviews_hide_authors_the_viewer_cannot_see(self, api_client, privacy_graph):
        for user in privacy_graph.values():
            Review.objects.create(user=user, media_type='movie', tmdb_id=550, content=f'{user.username} review')

        api_client.force_authenticate(user=privacy_graph['viewer'])
        response = api_client.get('/api/tracking/reviews/?media_type=movie&tmdb_id=550')

        assert response.status_code == 200
        contents = {row['content'] for row in response.data['results']}
        assert contents == {'viewer review', 'public review', 'friend review'}

    def test_reviews_require_auth(self, api_client):
        assert api_client.get('/api/tracking/reviews/').status_code == 401

    @pytest.mark.parametrize('query', ['?tmdb_id=abc', '?media_type=book'])
    def test_reviews_reject_invalid_filters(self, api_client, privacy_graph, query):
        api_client.force_authenticate(user=privacy_graph['viewer'])
        assert api_client.get(f'/api/tracking/reviews/{query}').status_code == 400

    def test_feed_does_not_query_per_entry(self, api_client, privacy_graph):
        api_client.force_authenticate(user=privacy_graph['viewer'])
        public = privacy_graph['public']

        def add_entries(start, count):
            for i in range(start, start + count):
                show = TVShowFactory(tmdb_id=700 + i, name=f'Show {i}')
                season = SeasonFactory(show=show, tmdb_id=800 + i, season_number=1, name='Season 1')
                EpisodeFactory(season=season, tmdb_id=900 + i, episode_number=1, name='Pilot')
                EpisodeWatchEntryFactory(
                    user=public, tmdb_id=700 + i, season_number=1, episode_number=1,
                )

        def query_count():
            with CaptureQueriesContext(connection) as ctx:
                response = api_client.get('/api/social/feed/')
                assert response.status_code == 200
            return len(ctx.captured_queries)

        add_entries(0, 2)
        before = query_count()
        add_entries(2, 6)
        assert query_count() == before
