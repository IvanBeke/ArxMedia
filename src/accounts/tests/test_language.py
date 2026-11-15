import pytest
from django.utils import translation
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

WEAK_PASSWORD = {'current_password': 'testpass123', 'new_password': '12345678'}


def session_client(user):
    """A client with a real session: the middleware reads the user from the session, not from force_authenticate."""
    client = APIClient()
    assert client.login(username=user.username, password='testpass123')
    return client


class TestUserLanguageMiddleware:
    def test_english_user_gets_english_messages(self, user):
        response = session_client(user).post('/api/auth/password/change/', WEAK_PASSWORD)

        assert response.status_code == 400
        assert 'This password is entirely numeric.' in response.json()['new_password']
        assert response['Content-Language'] == 'en'

    def test_spanish_user_gets_spanish_messages(self, user):
        user.language = 'es'
        user.save(update_fields=['language'])

        response = session_client(user).post('/api/auth/password/change/', WEAK_PASSWORD)

        assert response.status_code == 400
        assert 'Esta contraseña es completamente numérica.' in response.json()['new_password']
        assert response['Content-Language'] == 'es'

    def test_project_messages_follow_the_language(self, user):
        user.language = 'es'
        user.save(update_fields=['language'])

        response = session_client(user).post('/api/auth/users/nobody/follow/')

        assert response.status_code == 404
        assert response.json()['detail'] == 'Usuario no encontrado.'

    def test_anonymous_requests_use_english(self):
        response = APIClient().get('/api/auth/me/')

        assert response.status_code == 401
        assert response['Content-Language'] == 'en'
        assert response.json()['detail'] == 'Authentication credentials were not provided.'

    def test_the_language_does_not_leak_into_the_next_request(self, user):
        user.language = 'es'
        user.save(update_fields=['language'])

        session_client(user).get('/api/auth/me/')
        assert translation.get_language() == 'en'

        response = APIClient().get('/api/auth/me/')
        assert response.json()['detail'] == 'Authentication credentials were not provided.'

    def test_a_language_query_parameter_is_ignored(self, user):
        response = session_client(user).post('/api/auth/password/change/?language=es', WEAK_PASSWORD)

        assert 'This password is entirely numeric.' in response.json()['new_password']
