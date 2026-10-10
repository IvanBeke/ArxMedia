from unittest.mock import patch

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

from .base import BaseTestCase, User


class CustomListTests(BaseTestCase):
    def test_create_list(self):
        data = {'name': 'My Favorite Movies', 'description': 'Best movies ever', 'privacy': 'public'}
        response = self.client.post('/api/tracking/lists/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomList.objects.count(), 1)

    def test_create_list_with_collaborators(self):
        response = self.client.post('/api/tracking/lists/', {
            'name': 'Shared List',
            'collaborator_ids': [self.user2.id],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        lst = CustomList.objects.get(name='Shared List')
        self.assertTrue(ListCollaborator.objects.filter(custom_list=lst, user=self.user2).exists())

    def test_list_privacy_public(self):
        CustomList.objects.create(user=self.user2, name='Public List', privacy='public')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_privacy_private(self):
        CustomList.objects.create(user=self.user2, name='Private List', privacy='private')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

    def test_owner_sees_own_private_list(self):
        CustomList.objects.create(user=self.user, name='My Private List', privacy='private')
        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_update_list_as_owner(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        data = {'name': 'Updated List', 'privacy': 'private'}
        response = self.client.patch(f'/api/tracking/lists/{lst.id}/', data)
        self.assertEqual(response.status_code, 200)
        lst.refresh_from_db()
        self.assertEqual(lst.name, 'Updated List')

    def test_update_list_replaces_collaborators_atomically(self):
        third_user = User.objects.create_user(username='testuser3', password='testpass123')
        lst = CustomList.objects.create(user=self.user, name='Collaborative List')
        ListCollaborator.objects.create(custom_list=lst, user=self.user2)

        response = self.client.patch(
            f'/api/tracking/lists/{lst.id}/',
            {'name': 'Updated Collaborative List', 'collaborator_ids': [third_user.id]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(lst.collaboratorships.values_list('user_id', flat=True)),
            [third_user.id],
        )

    def test_update_list_rejects_owner_as_collaborator_without_partial_update(self):
        lst = CustomList.objects.create(user=self.user, name='Original List')

        response = self.client.patch(
            f'/api/tracking/lists/{lst.id}/',
            {'name': 'Should Not Persist', 'collaborator_ids': [self.user.id]},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        lst.refresh_from_db()
        self.assertEqual(lst.name, 'Original List')

    def test_cannot_create_list_with_followers_privacy(self):
        response = self.client.post('/api/tracking/lists/', {
            'name': 'Legacy Privacy',
            'privacy': 'followers',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('privacy', response.data)

    def test_public_list_hidden_when_owner_account_is_private(self):
        self.user2.account_visibility = 'private'
        self.user2.save(update_fields=['account_visibility'])
        CustomList.objects.create(user=self.user2, name='Hidden Public', privacy='public')

        response = self.client.get('/api/tracking/lists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)

    def test_public_list_visible_to_mutual_friend_when_owner_friends_only(self):
        self.user2.account_visibility = 'friends_only'
        self.user2.save(update_fields=['account_visibility'])
        target = CustomList.objects.create(user=self.user2, name='Friends Public', privacy='public')

        not_friend = self.client.get('/api/tracking/lists/')
        self.assertEqual(not_friend.status_code, 200)
        self.assertEqual(len(not_friend.data['results']), 0)

        Follow.objects.create(follower=self.user, following=self.user2)
        Follow.objects.create(follower=self.user2, following=self.user)

        as_friend = self.client.get('/api/tracking/lists/')
        self.assertEqual(as_friend.status_code, 200)
        self.assertEqual(len(as_friend.data['results']), 1)
        self.assertEqual(as_friend.data['results'][0]['id'], target.id)

    def test_collaborator_can_access_private_list(self):
        private_list = CustomList.objects.create(user=self.user2, name='Private Collab', privacy='private')
        ListCollaborator.objects.create(custom_list=private_list, user=self.user)

        list_response = self.client.get('/api/tracking/lists/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data['results']), 1)
        self.assertEqual(list_response.data['results'][0]['id'], private_list.id)

        detail_response = self.client.get(f'/api/tracking/lists/{private_list.id}/')
        self.assertEqual(detail_response.status_code, 200)

    def test_cannot_update_others_list(self):
        lst = CustomList.objects.create(user=self.user2, name='Other List')
        data = {'name': 'Hacked'}
        response = self.client.patch(f'/api/tracking/lists/{lst.id}/', data)
        self.assertEqual(response.status_code, 403)

    def test_delete_list_as_owner(self):
        lst = CustomList.objects.create(user=self.user, name='To Delete')
        response = self.client.delete(f'/api/tracking/lists/{lst.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CustomList.objects.count(), 0)


class ListItemTests(BaseTestCase):
    def test_sorts_provider_rating_by_item_media_type(self):
        custom_list = CustomList.objects.create(user=self.user, name='Provider Rating List')
        Movie.objects.create(tmdb_id=8001, title='Movie 8001', vote_average=8.1)
        TVShow.objects.create(tmdb_id=8001, name='Show 8001', vote_average=6.5)
        Movie.objects.create(tmdb_id=8002, title='Movie 8002', vote_average=7.0)
        ListItem.objects.create(custom_list=custom_list, media_type='tv', tmdb_id=8001)
        ListItem.objects.create(custom_list=custom_list, media_type='movie', tmdb_id=8002)

        response = self.client.get(
            f'/api/tracking/lists/{custom_list.id}/items/?sort=provider_rating&direction=asc'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(item['media_type'], item['tmdb_id']) for item in response.data['results']],
            [('tv', 8001), ('movie', 8002)],
        )

    def test_add_item_to_missing_list_returns_403(self):
        response = self.client.post('/api/tracking/lists/999999/items/', {'media_type': 'movie', 'tmdb_id': 123})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ListItem.objects.count(), 0)

    def test_add_item_to_list(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        data = {'media_type': 'movie', 'tmdb_id': 123}
        response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ListItem.objects.count(), 1)

    def test_add_movie_to_list_syncs_missing_metadata(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')

        def _create_movie(tmdb_id):
            return Movie.objects.create(tmdb_id=tmdb_id, title='Synced Movie')

        with patch('media.tmdb.tmdb.sync_movie', side_effect=_create_movie) as mock_sync:
            response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 124})
        self.assertEqual(response.status_code, 201)
        mock_sync.assert_called_once_with(124)
        self.assertTrue(Movie.objects.filter(tmdb_id=124).exists())
        self.assertEqual(response.data.get('title'), 'Synced Movie')

    def test_add_movie_to_list_skips_sync_when_present(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        Movie.objects.create(tmdb_id=125, title='Existing Movie')
        with patch('media.tmdb.tmdb.sync_movie') as mock_sync:
            response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 125})
        self.assertEqual(response.status_code, 201)
        mock_sync.assert_not_called()

    def test_add_tv_to_list_syncs_missing_metadata_without_credits(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        with patch('media.tmdb.tmdb.sync_tv_show') as mock_sync:
            response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'tv', 'tmdb_id': 457})
        self.assertEqual(response.status_code, 201)
        mock_sync.assert_called_once_with(457)

    def test_add_to_list_creates_item_when_sync_fails(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        with patch('media.tmdb.tmdb.sync_movie', side_effect=Exception('boom')):
            response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 126})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ListItem.objects.filter(custom_list=lst, media_type='movie', tmdb_id=126).exists())

    def test_remove_item_from_list(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        item = ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        response = self.client.delete(f'/api/tracking/lists/{lst.id}/items/{item.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(ListItem.objects.count(), 0)

    def test_sort_list_items_by_date(self):
        lst = CustomList.objects.create(user=self.user, name='Test List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=123)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=456)
        
        # Default sort should be added_at ascending
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(response.status_code, 200)
        # Should have at least our 2 items
        self.assertGreaterEqual(len(response.data), 2)
        
        # Sort by added_at ascending
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=added_at')
        self.assertEqual(response.status_code, 200)
        
        # Invalid sort falls back safely
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=media_type')
        self.assertEqual(response.status_code, 200)

    def test_list_items_paginated_envelope(self):
        lst = CustomList.objects.create(user=self.user, name='Paginated List')
        for index in range(25):
            ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=9000 + index)

        first_page = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.data['count'], 25)
        self.assertEqual(len(first_page.data['results']), 20)
        self.assertIsNotNone(first_page.data['next'])
        self.assertIsNone(first_page.data['previous'])

        second_page = self.client.get(f'/api/tracking/lists/{lst.id}/items/?page=2')
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.data['count'], 25)
        self.assertEqual(len(second_page.data['results']), 5)
        self.assertIsNone(second_page.data['next'])
        page_two_ids = {item['tmdb_id'] for item in second_page.data['results']}
        page_one_ids = {item['tmdb_id'] for item in first_page.data['results']}
        self.assertEqual(len(page_one_ids | page_two_ids), 25)

    def test_cannot_access_others_list_items(self):
        lst = CustomList.objects.create(user=self.user2, name='Other List', privacy='private')
        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual(response.status_code, 403)

    def test_list_detail_excludes_items_payload(self):
        lst = CustomList.objects.create(user=self.user, name='Detail List')
        Movie.objects.create(tmdb_id=888, title='Detail Movie', vote_average=8.1, release_date='2021-05-01')
        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=888, status='plan_to_watch', status_changed_at=timezone.now())
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=888)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('items', response.data)
        self.assertEqual(response.data['item_count'], 1)

    def test_duplicate_add_to_list_returns_validation_error(self):
        lst = CustomList.objects.create(user=self.user, name='Unique List')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=222)

        response = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 222})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'), 'Item is already in this list.')

    def test_list_items_title_sort_works(self):
        lst = CustomList.objects.create(user=self.user, name='Sort by title')
        Movie.objects.create(tmdb_id=7101, title='Zulu')
        Movie.objects.create(tmdb_id=7102, title='Alpha')
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7101)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7102)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=title&direction=asc')
        self.assertEqual(response.status_code, 200)
        items = response.data.get('results', response.data)
        self.assertEqual([item['tmdb_id'] for item in items], [7102, 7101])

    def test_list_items_filter_genres(self):
        lst = CustomList.objects.create(user=self.user, name='Genre List')
        drama = Genre.objects.create(tmdb_id=911, name='Drama')
        thriller = Genre.objects.create(tmdb_id=912, name='Thriller')

        movie = Movie.objects.create(tmdb_id=7201, title='Drama Film')
        movie.genres.add(drama)
        show = TVShow.objects.create(tmdb_id=7202, name='Thriller Show')
        show.genres.add(thriller)

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7201)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7202)

        filtered = self.client.get(f'/api/tracking/lists/{lst.id}/items/?genres=Thriller')
        self.assertEqual(filtered.status_code, 200)
        items = filtered.data.get('results', filtered.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tmdb_id'], 7202)

    def test_list_items_filter_status(self):
        lst = CustomList.objects.create(user=self.user, name='Status List')
        Movie.objects.create(tmdb_id=7301, title='Planned Movie')
        Movie.objects.create(tmdb_id=7302, title='Watched Movie')
        TVShow.objects.create(tmdb_id=7303, name='Planned Show')
        TVShow.objects.create(tmdb_id=7304, name='Watched Show')

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7301)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7302)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7303)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7304)

        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=7301, status='plan_to_watch', status_changed_at=timezone.now())
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=7302, watched_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=7303, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=7304, status='watched', watched_episodes=1, total_episodes=1)

        planned = self.client.get(f'/api/tracking/lists/{lst.id}/items/?status=plan_to_watch')
        self.assertEqual(planned.status_code, 200)
        planned_items = planned.data.get('results', planned.data)
        self.assertEqual({item['tmdb_id'] for item in planned_items}, {7301, 7303})

        watched = self.client.get(f'/api/tracking/lists/{lst.id}/items/?status=watched')
        self.assertEqual(watched.status_code, 200)
        watched_items = watched.data.get('results', watched.data)
        self.assertEqual({item['tmdb_id'] for item in watched_items}, {7302, 7304})

    def test_list_items_filter_watching_dropped_and_ignores_other_users(self):
        lst = CustomList.objects.create(user=self.user, name='Show Status List')
        for tmdb_id, status in ((7311, 'watching'), (7312, 'dropped'), (7313, 'watched')):
            TVShow.objects.create(tmdb_id=tmdb_id, name=f'Show {tmdb_id}')
            ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=tmdb_id)
            UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=tmdb_id, status=status)
        TVShow.objects.create(tmdb_id=7314, name='Someone Else Watching')
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7314)
        UserMediaStatus.objects.create(user=self.user2, media_type='tv', tmdb_id=7314, status='watching')

        def ids(query):
            response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?{query}')
            self.assertEqual(response.status_code, 200)
            return {item['tmdb_id'] for item in response.data.get('results', response.data)}

        self.assertEqual(ids('status=watching'), {7311})
        self.assertEqual(ids('status=dropped'), {7312})
        self.assertEqual(ids('status=watching&status=dropped'), {7311, 7312})

    def test_list_status_filters_run_inside_the_list_query(self):
        lst = CustomList.objects.create(user=self.user, name='Big List')
        for tmdb_id in range(7500, 7506):
            Movie.objects.create(tmdb_id=tmdb_id, title=f'Movie {tmdb_id}')
            ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=tmdb_id)
            WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=tmdb_id, watched_at=timezone.now())

        def query_count(query):
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(f'/api/tracking/lists/{lst.id}/items/{query}')
            self.assertEqual(response.status_code, 200)
            return len(ctx.captured_queries)

        # Filters are EXISTS subqueries: no extra round trips to collect ids.
        self.assertEqual(query_count('?status=watched&missing_rating=true'), query_count(''))

    def test_list_items_missing_rating_excludes_plan_to_watch(self):
        lst = CustomList.objects.create(user=self.user, name='Missing Rating List')
        Movie.objects.create(tmdb_id=7401, title='Planned Movie')
        Movie.objects.create(tmdb_id=7402, title='Watched Movie')
        TVShow.objects.create(tmdb_id=7403, name='Planned Show')
        TVShow.objects.create(tmdb_id=7404, name='Watched Show')

        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7401)
        ListItem.objects.create(custom_list=lst, media_type='movie', tmdb_id=7402)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7403)
        ListItem.objects.create(custom_list=lst, media_type='tv', tmdb_id=7404)

        UserMediaStatus.objects.create(user=self.user, media_type='movie', tmdb_id=7401, status='plan_to_watch', status_changed_at=timezone.now())
        WatchEntry.objects.create(user=self.user, media_type='movie', tmdb_id=7402, watched_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=7403, status='plan_to_watch', status_changed_at=timezone.now())
        UserMediaStatus.objects.create(user=self.user, media_type='tv', tmdb_id=7404, status='watched', watched_episodes=1, total_episodes=1)
        Rating.objects.create(user=self.user, media_type='tv', tmdb_id=7404, score=8)

        response = self.client.get(f'/api/tracking/lists/{lst.id}/items/?missing_rating=true')
        self.assertEqual(response.status_code, 200)
        items = response.data.get('results', response.data)
        self.assertEqual({item['tmdb_id'] for item in items}, {7402})


class ListItemCustomOrderTests(BaseTestCase):
    def test_custom_order_assigned_sequentially(self):
        lst = CustomList.objects.create(user=self.user, name='Order Seq')
        for tmdb in [101, 102, 103]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        orders = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('tmdb_id', 'custom_order'))
        self.assertEqual(orders, [(101, 0), (102, 1), (103, 2)])

    def test_sort_by_custom_order(self):
        lst = CustomList.objects.create(user=self.user, name='Sort Order')
        for tmdb in [201, 202, 203]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        # default should be custom_order asc
        resp = self.client.get(f'/api/tracking/lists/{lst.id}/items/')
        self.assertEqual([i['tmdb_id'] for i in resp.data['results']], [201, 202, 203])
        # explicit asc
        resp = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=custom_order&direction=asc')
        self.assertEqual([i['tmdb_id'] for i in resp.data['results']], [201, 202, 203])
        # desc
        resp = self.client.get(f'/api/tracking/lists/{lst.id}/items/?sort=custom_order&direction=desc')
        self.assertEqual([i['tmdb_id'] for i in resp.data['results']], [203, 202, 201])

    def test_gaps_left_after_delete_and_append(self):
        lst = CustomList.objects.create(user=self.user, name='Gaps')
        for tmdb in [301, 302, 303]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        mid = ListItem.objects.get(custom_list=lst, tmdb_id=302)
        self.client.delete(f'/api/tracking/lists/{lst.id}/items/{mid.id}/')
        orders = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('custom_order', flat=True))
        self.assertEqual(orders, [0, 2])  # gap at 1
        self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 304})
        new = ListItem.objects.get(custom_list=lst, tmdb_id=304)
        self.assertEqual(new.custom_order, 3)  # max+1, gap preserved

    def test_reorder_items(self):
        lst = CustomList.objects.create(user=self.user, name='Reorder')
        for tmdb in [401, 402, 403]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('id', flat=True))
        rev = list(reversed(ids))
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': rev}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['custom_order'], rev)
        ordered = list(ListItem.objects.filter(custom_list=lst).order_by('custom_order').values_list('tmdb_id', flat=True))
        self.assertEqual(ordered, [403, 402, 401])

    def test_reorder_requires_all_ids(self):
        lst = CustomList.objects.create(user=self.user, name='Reorder Validation')
        for tmdb in [501, 502]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        # missing one id
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': [ids[0]]}, format='json')
        self.assertEqual(resp.status_code, 400)
        # duplicate
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': [ids[0], ids[0]]}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_reorder_permission(self):
        lst = CustomList.objects.create(user=self.user, name='Reorder Perm')
        for tmdb in [601, 602]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        self.authenticate(self.user2)
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': list(reversed(ids))}, format='json')
        self.assertEqual(resp.status_code, 403)
        # collaborator can reorder
        ListCollaborator.objects.create(custom_list=lst, user=self.user2)
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'custom_order': list(reversed(ids))}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_order_alias_not_accepted(self):
        lst = CustomList.objects.create(user=self.user, name='Alias')
        for tmdb in [701, 702]:
            self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': tmdb})
        ids = list(ListItem.objects.filter(custom_list=lst).values_list('id', flat=True))
        resp = self.client.post(f'/api/tracking/lists/{lst.id}/items/reorder/', {'order': ids}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('custom_order', resp.data)


class ListCollaborationTest(BaseTestCase):
    def test_collaborator_can_add_items_to_shared_list(self):
        lst = CustomList.objects.create(user=self.user, name='Shared List')
        ListCollaborator.objects.create(custom_list=lst, user=self.user2)

        self.authenticate(self.user2)
        add_item = self.client.post(f'/api/tracking/lists/{lst.id}/items/', {'media_type': 'movie', 'tmdb_id': 987})
        self.assertEqual(add_item.status_code, 201)
