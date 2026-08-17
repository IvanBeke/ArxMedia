from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from social.models import Follow

User = get_user_model()


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()

    def authenticate(self, user=None):
        if user is None:
            user = self.user
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_register_user(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'password2': 'newpass123'
        }
        response = self.client.post('/api/auth/register/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 2)

    def test_login_user(self):
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post('/api/auth/login/', data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_get_profile(self):
        self.authenticate()
        response = self.client.get(f'/api/auth/users/{self.user.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertIn('viewer_relationship', response.data)
        self.assertIn('permissions', response.data)
        self.assertIn('stats', response.data)
        self.assertIn('recent_activity', response.data)
        self.assertIn('visible_lists', response.data)

    def test_follow_user(self):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.authenticate()
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.following.filter(following=user2).exists())

    def test_unfollow_user(self):
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.authenticate()
        # First follow
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.following.filter(following=user2).exists())
        # Then unfollow
        response = self.client.post(f'/api/auth/users/{user2.username}/follow/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user.following.filter(following=user2).exists())

    def test_follow_self(self):
        self.authenticate()
        response = self.client.post(f'/api/auth/users/{self.user.username}/follow/')
        self.assertEqual(response.status_code, 400)

    def test_password_change_success(self):
        self.authenticate()
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('betterpass123'))
        self.assertFalse(self.user.check_password('testpass123'))

    def test_password_change_requires_auth(self):
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'testpass123',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 401)

    def test_password_change_wrong_current_password(self):
        self.authenticate()
        response = self.client.post('/api/auth/password/change/', {
            'current_password': 'wrongpass',
            'new_password': 'betterpass123'
        })
        self.assertEqual(response.status_code, 400)

    def test_update_preferred_region(self):
        self.authenticate()
        response = self.client.patch('/api/auth/me/', {
            'preferred_region': 'es'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['preferred_region'], 'ES')

        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_region, 'ES')

    def test_update_account_visibility(self):
        self.authenticate()
        response = self.client.patch('/api/auth/me/', {
            'account_visibility': 'friends_only'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['account_visibility'], 'friends_only')

        self.user.refresh_from_db()
        self.assertEqual(self.user.account_visibility, 'friends_only')

    def test_friends_only_profile_hidden_for_non_friend(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['permissions']['can_view_activity'])
        self.assertEqual(response.data['recent_activity'], [])
        self.assertEqual(response.data['visible_lists'], [])

    def test_friends_only_profile_visible_for_mutual_friend(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=self.user, following=target)
        Follow.objects.create(follower=target, following=self.user)
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['permissions']['can_view_activity'])
        self.assertTrue(response.data['viewer_relationship']['is_friend'])

    def test_followers_following_endpoints_respect_privacy(self):
        target = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        self.authenticate()

        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 403)
        self.assertEqual(following_response.status_code, 403)

        Follow.objects.create(follower=self.user, following=target)
        Follow.objects.create(follower=target, following=self.user)
        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 200)
        self.assertEqual(following_response.status_code, 200)

    def test_private_profile_hidden_for_anonymous_user(self):
        target = User.objects.create_user(
            username='private_target',
            email='private-target@example.com',
            password='pass123',
            account_visibility='private',
        )

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['permissions']['can_view_activity'])
        self.assertFalse(response.data['permissions']['can_view_lists'])
        self.assertEqual(response.data['stats']['ratings_count'], None)
        self.assertEqual(response.data['recent_activity'], [])
        self.assertEqual(response.data['visible_lists'], [])

    def test_private_profile_visible_for_owner(self):
        self.user.account_visibility = 'private'
        self.user.save(update_fields=['account_visibility'])
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{self.user.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['permissions']['can_view_activity'])
        self.assertTrue(response.data['permissions']['can_view_lists'])
        self.assertTrue(response.data['viewer_relationship']['is_self'])

    def test_friends_only_profile_hidden_for_one_way_follow(self):
        target = User.objects.create_user(
            username='friends_target',
            email='friends-target@example.com',
            password='pass123',
            account_visibility='friends_only',
        )
        Follow.objects.create(follower=self.user, following=target)
        self.authenticate()

        response = self.client.get(f'/api/auth/users/{target.username}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['permissions']['can_view_activity'])
        self.assertFalse(response.data['viewer_relationship']['is_friend'])

    def test_public_followers_endpoint_returns_paginated_payload(self):
        target = User.objects.create_user(
            username='public_target',
            email='public-target@example.com',
            password='pass123',
            account_visibility='public',
        )

        for index in range(25):
            follower = User.objects.create_user(
                username=f'follower_{index}',
                email=f'follower_{index}@example.com',
                password='pass123',
            )
            Follow.objects.create(follower=follower, following=target)

        response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 20)

        page_two = self.client.get(f'/api/auth/users/{target.username}/followers/?page=2')
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(len(page_two.data['results']), 5)

    def test_private_followers_and_following_endpoints_forbidden(self):
        target = User.objects.create_user(
            username='private_graph_target',
            email='private-graph-target@example.com',
            password='pass123',
            account_visibility='private',
        )
        self.authenticate()

        followers_response = self.client.get(f'/api/auth/users/{target.username}/followers/')
        following_response = self.client.get(f'/api/auth/users/{target.username}/following/')
        self.assertEqual(followers_response.status_code, 403)
        self.assertEqual(following_response.status_code, 403)
