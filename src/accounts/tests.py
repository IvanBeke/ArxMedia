from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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
