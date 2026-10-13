from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from media.models import Genre, Movie, TVShow
from social.models import Follow
from tracking.models import (
    CustomList,
    ListCollaborator,
    ListItem,
    Rating,
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()


pytestmark = pytest.mark.django_db

class CustomListTests:
    def test_create_list(self, user, auth_client, user2, tmdb_noop):
        data = {'name': 'My Favorite Movies', 'description': 'Best movies ever', 'privacy': 'public'}
        response = auth_client.post('/api/tracking/lists/', data)
        assert response.status_code == 201
        assert CustomList.objects.count() == 1

    def test_create_list_with_collaborators(self, user, user2, auth_client, tmdb_noop):
        response = auth_client.post('/api/tracking/lists/', {
            'name': 'Shared List',
            'collaborator_ids': [user2.id],
        }, format='json')

        assert response.status_code == 201
        lst = CustomList.objects.get(name='Shared List')
        assert ListCollaborator.objects.filter(custom_list=lst, user=user2).exists()

    def test_list_privacy_public(self, user, user2, auth_client, tmdb_noop):
        CustomList.objects.create(user=user2, name='Public List', privacy='public')
        response = auth_client.get('/api/tracking/lists/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_list_privacy_private(self, user, user2, auth_client, tmdb_noop):
        CustomList.objects.create(user=user2, name='Private List', privacy='private')
        response = auth_client.get('/api/tracking/lists/')
        assert response.status_code == 200
        assert len(response.data['results']) == 0

    def test_owner_sees_own_private_list(self, user, auth_client, user2, tmdb_noop):
        CustomList.objects.create(user=user, name='My Private List', privacy='private')
        response = auth_client.get('/api/tracking/lists/')
        assert response.status_code == 200
        assert len(response.data['results']) == 1

    def test_lists_annotate_membership_for_item(self, user, auth_client, user2, tmdb_noop):
        contained = CustomList.objects.create(user=user, name='Contained')
        other = CustomList.objects.create(user=user, name='Other')
        item = ListItem.objects.create(custom_list=contained, media_type='movie', tmdb_id=123)

        response = auth_client.get('/api/tracking/lists/', {'media_type': 'movie', 'tmdb_id': 123})

        assert response.status_code == 200
        by_id = {row['id']: row for row in response.data['results']}
        assert by_id[contained.id]['contains_item'] is True
        assert by_id[contained.id]['contains_item_id'] == item.id
        assert by_id[other.id]['contains_item'] is False
        assert by_id[other.id]['contains_item_id'] is None

    def test_lists_membership_ignores_invalid_params(self, user, auth_client, user2, tmdb_noop):
        CustomList.objects.create(user=user, name='My List')

        response = auth_client.get('/api/tracking/lists/', {'media_type': 'movie'})

        assert response.status_code == 200
        assert response.data['results'][0]['contains_item'] is False
        assert response.data['results'][0]['contains_item_id'] is None

    def test_update_list_as_owner(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        data = {'name': 'Updated List', 'privacy': 'private'}
        response = auth_client.patch(f'/api/tracking/lists/{lst.id}/', data)
        assert response.status_code == 200
        lst.refresh_from_db()
        assert lst.name == 'Updated List'

    def test_update_list_replaces_collaborators_atomically(self, user, user2, auth_client, tmdb_noop):
        third_user = User.objects.create_user(username='testuser3', password='testpass123')
        lst = CustomList.objects.create(user=user, name='Collaborative List')
        ListCollaborator.objects.create(custom_list=lst, user=user2)

        response = auth_client.patch(
            f'/api/tracking/lists/{lst.id}/',
            {'name': 'Updated Collaborative List', 'collaborator_ids': [third_user.id]},
            format='json',
        )

        assert response.status_code == 200
        assert list(lst.collaboratorships.values_list('user_id', flat=True)) == [third_user.id]

    def test_update_list_rejects_owner_as_collaborator_without_partial_update(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Original List')

        response = auth_client.patch(
            f'/api/tracking/lists/{lst.id}/',
            {'name': 'Should Not Persist', 'collaborator_ids': [user.id]},
            format='json',
        )

        assert response.status_code == 400
        lst.refresh_from_db()
        assert lst.name == 'Original List'

    def test_cannot_create_list_with_followers_privacy(self, user, auth_client, user2, tmdb_noop):
        response = auth_client.post('/api/tracking/lists/', {
            'name': 'Legacy Privacy',
            'privacy': 'followers',
        })
        assert response.status_code == 400
        assert 'privacy' in response.data

    def test_public_list_hidden_when_owner_account_is_private(self, user, user2, auth_client, tmdb_noop):
        user2.account_visibility = 'private'
        user2.save(update_fields=['account_visibility'])
        CustomList.objects.create(user=user2, name='Hidden Public', privacy='public')

        response = auth_client.get('/api/tracking/lists/')
        assert response.status_code == 200
        assert len(response.data['results']) == 0

    def test_public_list_visible_to_mutual_friend_when_owner_friends_only(self, user, user2, auth_client, tmdb_noop):
        user2.account_visibility = 'friends_only'
        user2.save(update_fields=['account_visibility'])
        target = CustomList.objects.create(user=user2, name='Friends Public', privacy='public')

        not_friend = auth_client.get('/api/tracking/lists/')
        assert not_friend.status_code == 200
        assert len(not_friend.data['results']) == 0

        Follow.objects.create(follower=user, following=user2)
        Follow.objects.create(follower=user2, following=user)

        as_friend = auth_client.get('/api/tracking/lists/')
        assert as_friend.status_code == 200
        assert len(as_friend.data['results']) == 1
        assert as_friend.data['results'][0]['id'] == target.id

    def test_collaborator_can_access_private_list(self, user, user2, auth_client, tmdb_noop):
        private_list = CustomList.objects.create(user=user2, name='Private Collab', privacy='private')
        ListCollaborator.objects.create(custom_list=private_list, user=user)

        list_response = auth_client.get('/api/tracking/lists/')
        assert list_response.status_code == 200
        assert len(list_response.data['results']) == 1
        assert list_response.data['results'][0]['id'] == private_list.id

        detail_response = auth_client.get(f'/api/tracking/lists/{private_list.id}/')
        assert detail_response.status_code == 200

    def test_cannot_update_others_list(self, user, user2, auth_client, tmdb_noop):
        lst = CustomList.objects.create(user=user2, name='Other List')
        data = {'name': 'Hacked'}
        response = auth_client.patch(f'/api/tracking/lists/{lst.id}/', data)
        assert response.status_code == 403

    def test_delete_list_as_owner(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='To Delete')
        response = auth_client.delete(f'/api/tracking/lists/{lst.id}/')
        assert response.status_code == 204
        assert CustomList.objects.count() == 0


class ListItemTests:
    def test_sorts_provider_rating_by_item_media_type(self, user, auth_client, user2, tmdb_noop):
        custom_list = CustomList.objects.create(user=user, name='Provider Rating List')
        Movie.objects.create(tmdb_id=8001, title='Movie 8001', vote_average=8.1)
        TVShow.objects.create(tmdb_id=8001, name='Show 8001', vote_average=6.5)
        Movie.objects.create(tmdb_id=8002, title='Movie 8002', vote_average=7.0)
        ListItem.objects.create(custom_list=custom_list, media_type='tv', tmdb_id=8001)
        ListItem.objects.create(custom_list=custom_list, media_type='movie', tmdb_id=8002)

        response = auth_client.get(
            f'/api/tracking/lists/{custom_list.id}/items/?sort=provider_rating&direction=asc'
        )

        assert response.status_code == 200
        assert [(item['media_type'], item['tmdb_id']) for item in response.data['results']] == [('tv', 8001), ('movie', 8002)]

    def test_add_item_to_missing_list_returns_403(self, user, auth_client, user2, tmdb_noop):
        response = auth_client.post('/api/tracking/lists/999999/items/', {'media_type': 'movie', 'tmdb_id': 123})
        assert response.status_code == 403
        assert ListItem.objects.count() == 0

    def test_add_item_to_list(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', data)
        assert response.status_code == 201
        assert ListItem.objects.count() == 1

    def test_add_movie_to_list_syncs_missing_metadata(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')

        def _create_movie(tmdb_id):
            return Movie.objects.create(tmdb_id=tmdb_id, title='Synced Movie')

        with patch('media.tmdb.tmdb.sync_movie', side_effect=_create_movie) as mock_sync:
            response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 124})
        assert response.status_code == 201
        mock_sync.assert_called_once_with(124)
        assert Movie.objects.filter(tmdb_id=124).exists()
        assert response.data.get('title') == 'Synced Movie'

    def test_add_movie_to_list_skips_sync_when_present(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        Movie.objects.create(tmdb_id=125, title='Existing Movie')
        with patch('media.tmdb.tmdb.sync_movie') as mock_sync:
            response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 125})
        assert response.status_code == 201
        mock_sync.assert_not_called()

    def test_add_tv_to_list_syncs_missing_metadata_without_credits(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        with patch('media.tmdb.tmdb.sync_tv_show') as mock_sync:
            response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'tv', 'tmdb_id': 457})
        assert response.status_code == 201
        mock_sync.assert_called_once_with(457)

    def test_add_to_list_creates_item_when_sync_fails(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        with patch('media.tmdb.tmdb.sync_movie', side_effect=Exception('boom')):
            response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 126})
        assert response.status_code == 201
        assert ListItem.objects.filter(custom_list=lst, media_type='movie', tmdb_id=126).exists()

    def test_remove_item_from_list(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        item = ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        response = auth_client.delete(f'/api/tracking/lists/{lst.id}/items/{item.id}/')
        assert response.status_code == 204
        assert ListItem.objects.count() == 0

    def test_sort_list_items_by_date(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Test List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=456)
        
        # Default sort should be added_at ascending
        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/')
        assert response.status_code == 200
        # Should have at least our 2 items
        assert len(response.data) >= 2
        
        # Sort by added_at ascending
        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?sort=added_at')
        assert response.status_code == 200
        
        # Invalid sort falls back safely
        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?sort=media_type')
        assert response.status_code == 200

    def test_list_items_paginated_envelope(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Paginated List')
        for index in range(25):
            ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=9000 + index)

        first_page = auth_client.get(f'/api/tracking/lists/{lst.id}/items/')
        assert first_page.status_code == 200
        assert first_page.data['count'] == 25
        assert len(first_page.data['results']) == 20
        assert first_page.data['next'] is not None
        assert first_page.data['previous'] is None

        second_page = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?page=2')
        assert second_page.status_code == 200
        assert second_page.data['count'] == 25
        assert len(second_page.data['results']) == 5
        assert second_page.data['next'] is None
        page_two_ids = {item['tmdb_id'] for item in second_page.data['results']}
        page_one_ids = {item['tmdb_id'] for item in first_page.data['results']}
        assert len(page_one_ids | page_two_ids) == 25

    def test_cannot_access_others_list_items(self, user, user2, auth_client, tmdb_noop):
        lst = CustomList.objects.create(user=user2, name='Other List', privacy='private')
        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/')
        assert response.status_code == 403

    def test_list_detail_excludes_items_payload(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Detail List')
        Movie.objects.create(tmdb_id=888, title='Detail Movie', vote_average=8.1, release_date='2021-05-01')
        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=888, status='plan_to_watch', status_changed_at=timezone.now())
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=888)

        response = auth_client.get(f'/api/tracking/lists/{lst.id}/')
        assert response.status_code == 200
        assert 'items' not in response.data
        assert response.data['item_count'] == 1

    def test_duplicate_add_to_list_returns_validation_error(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Unique List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=222)

        response = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 222})
        assert response.status_code == 400
        assert response.data.get('detail') == 'Item is already in this list.'

    def test_list_items_title_sort_works(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Sort by title')
        Movie.objects.create(tmdb_id=7101, title='Zulu')
        Movie.objects.create(tmdb_id=7102, title='Alpha')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7101)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7102)

        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?sort=title&direction=asc')
        assert response.status_code == 200
        items = response.data.get('results', response.data)
        assert [item['tmdb_id'] for item in items] == [7102, 7101]

    def test_list_items_filter_genres(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Genre List')
        drama = Genre.objects.create(tmdb_id=911, name='Drama')
        thriller = Genre.objects.create(tmdb_id=912, name='Thriller')

        movie = Movie.objects.create(tmdb_id=7201, title='Drama Film')
        movie.genres.add(drama)
        show = TVShow.objects.create(tmdb_id=7202, name='Thriller Show')
        show.genres.add(thriller)

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7201)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7202)

        filtered = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?genres=Thriller')
        assert filtered.status_code == 200
        items = filtered.data.get('results', filtered.data)
        assert len(items) == 1
        assert items[0]['tmdb_id'] == 7202

    def test_list_items_filter_status(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Status List')
        Movie.objects.create(tmdb_id=7301, title='Planned Movie')
        Movie.objects.create(tmdb_id=7302, title='Watched Movie')
        TVShow.objects.create(tmdb_id=7303, name='Planned Show')
        TVShow.objects.create(tmdb_id=7304, name='Watched Show')

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7301)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7302)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7303)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7304)

        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=7301, status='plan_to_watch', status_changed_at=timezone.now())
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=7302, watched_at=timezone.now())
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=7303, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=7304, status='watched', watched_episodes=1, total_episodes=1)

        planned = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?status=plan_to_watch')
        assert planned.status_code == 200
        planned_items = planned.data.get('results', planned.data)
        assert {item['tmdb_id'] for item in planned_items} == {7301, 7303}

        watched = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?status=watched')
        assert watched.status_code == 200
        watched_items = watched.data.get('results', watched.data)
        assert {item['tmdb_id'] for item in watched_items} == {7302, 7304}

    def test_list_items_filter_watching_dropped_and_ignores_other_users(self, user, user2, auth_client, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Show Status List')
        for tmdb_id, status in ((7311, 'watching'), (7312, 'dropped'), (7313, 'watched')):
            TVShow.objects.create(tmdb_id=tmdb_id, name=f'Show {tmdb_id}')
            ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=tmdb_id)
            UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=tmdb_id, status=status)
        TVShow.objects.create(tmdb_id=7314, name='Someone Else Watching')
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7314)
        UserMediaStatus.objects.create(user=user2, media_type='tv', tmdb_id=7314, status='watching')

        def ids(query):
            response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?{query}')
            assert response.status_code == 200
            return {item['tmdb_id'] for item in response.data.get('results', response.data)}

        assert ids('status=watching') == {7311}
        assert ids('status=dropped') == {7312}
        assert ids('status=watching&status=dropped') == {7311, 7312}

    def test_list_status_filters_run_inside_the_list_query(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Big List')
        for tmdb_id in range(7500, 7506):
            Movie.objects.create(tmdb_id=tmdb_id, title=f'Movie {tmdb_id}')
            ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=tmdb_id)
            WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=tmdb_id, watched_at=timezone.now())

        def query_count(query):
            with CaptureQueriesContext(connection) as ctx:
                response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/{query}')
            assert response.status_code == 200
            return len(ctx.captured_queries)

        # Filters are EXISTS subqueries: no extra round trips to collect ids.
        assert query_count('?status=watched&missing_rating=true') == query_count('')

    def test_list_items_missing_rating_excludes_plan_to_watch(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Missing Rating List')
        Movie.objects.create(tmdb_id=7401, title='Planned Movie')
        Movie.objects.create(tmdb_id=7402, title='Watched Movie')
        TVShow.objects.create(tmdb_id=7403, name='Planned Show')
        TVShow.objects.create(tmdb_id=7404, name='Watched Show')

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7401)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7402)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7403)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7404)

        UserMediaStatus.objects.create(user=user, media_type='movie', tmdb_id=7401, status='plan_to_watch', status_changed_at=timezone.now())
        WatchEntry.objects.create(user=user, media_type='movie', tmdb_id=7402, watched_at=timezone.now())
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=7403, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=user, media_type='tv', tmdb_id=7404, status='watched', watched_episodes=1, total_episodes=1)
        Rating.objects.create(user=user, media_type='tv', tmdb_id=7404, score=8)

        response = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?missing_rating=true')
        assert response.status_code == 200
        items = response.data.get('results', response.data)
        assert {item['tmdb_id'] for item in items} == {7402}


class ListItemCustomOrderTests:
    def test_custom_order_assigned_sequentially(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Order Seq')
        for tmdb in [101, 102, 103]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        orders = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('tmdb_id', 'custom_order'))
        assert orders == [(101, 0), (102, 1), (103, 2)]

    def test_sort_by_custom_order(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Sort Order')
        for tmdb in [201, 202, 203]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        # default should be custom_order asc
        resp = auth_client.get(f'/api/tracking/lists/{lst.id}/items/')
        assert [i['tmdb_id'] for i in resp.data['results']] == [201, 202, 203]
        # explicit asc
        resp = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?sort=custom_order&direction=asc')
        assert [i['tmdb_id'] for i in resp.data['results']] == [201, 202, 203]
        # desc
        resp = auth_client.get(f'/api/tracking/lists/{lst.id}/items/?sort=custom_order&direction=desc')
        assert [i['tmdb_id'] for i in resp.data['results']] == [203, 202, 201]

    def test_gaps_left_after_delete_and_append(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Gaps')
        for tmdb in [301, 302, 303]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        mid = ListItem.objects.get(custom_list=lst, tmdb_id=302)
        auth_client.delete(f'/api/tracking/lists/{lst.id}/items/{mid.id}/')
        orders = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('custom_order', flat=True))
        assert orders == [0, 2]  # gap at 1
        auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 304})
        new = ListItem.objects.get(custom_list=lst, tmdb_id=304)
        assert new.custom_order == 3  # max+1, gap preserved

    def test_reorder_items(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Reorder')
        for tmdb in [401, 402, 403]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('id', flat=True))
        rev = list(reversed(ids))
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': rev}, format='json')
        assert resp.status_code == 200
        assert resp.data['custom_order'] == rev
        ordered = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('tmdb_id', flat=True))
        assert ordered == [403, 402, 401]

    def test_reorder_requires_all_ids(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Reorder Validation')
        for tmdb in [501, 502]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        # missing one id
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': [ids[0]]}, format='json')
        assert resp.status_code == 400
        # duplicate
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': [ids[0], ids[0]]}, format='json')
        assert resp.status_code == 400

    def test_reorder_permission(self, user, user2, auth_client, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Reorder Perm')
        for tmdb in [601, 602]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        auth_client.force_authenticate(user=user2)
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': list(reversed(ids))}, format='json')
        assert resp.status_code == 403
        # collaborator can reorder
        ListCollaborator.objects.create(custom_list=lst, user=user2)
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': list(reversed(ids))}, format='json')
        assert resp.status_code == 200

    def test_order_alias_not_accepted(self, user, auth_client, user2, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Alias')
        for tmdb in [701, 702]:
            auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        resp = auth_client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'order': ids}, format='json')
        assert resp.status_code == 400
        assert 'custom_order' in resp.data


class ListCollaborationTest:
    def test_collaborator_can_add_items_to_shared_list(self, user, user2, auth_client, tmdb_noop):
        lst = CustomList.objects.create(user=user, name='Shared List')
        ListCollaborator.objects.create(custom_list=lst, user=user2)

        auth_client.force_authenticate(user=user2)
        add_item = auth_client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 987})
        assert add_item.status_code == 201
