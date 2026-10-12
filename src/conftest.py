"""Shared pytest fixtures for ArxMedia."""

import pytest
from django.core.cache import cache as django_cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_cache():
    django_cache.clear()
    yield
    django_cache.clear()


@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch):
    """Fail any test that attempts real HTTP (CI has no TMDB key)."""

    def _blocked(self, *args, **kwargs):
        raise AssertionError("Real HTTP request blocked in tests (fake/mock TMDB/TVMaze instead)")

    monkeypatch.setattr("requests.Session.request", _blocked)


@pytest.fixture
def user(db):
    from accounts.tests.factories import UserFactory

    return UserFactory(username="testuser", email="test@example.com")


@pytest.fixture
def user2(db):
    from accounts.tests.factories import UserFactory

    return UserFactory(username="testuser2", email="user2@example.com")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def auth_client2(api_client, user2):
    api_client.force_authenticate(user=user2)
    return api_client


@pytest.fixture
def tmdb_noop(mocker):
    """Neutralize outbound TMDB sync calls."""
    targets = [
        "media.tmdb.tmdb.sync_movie",
        "media.tmdb.tmdb.sync_tv_show",
        "tracking.tasks.tmdb.sync_movie",
        "tracking.tasks.tmdb.sync_tv_show",
        "tracking.tasks.tmdb.sync_season",
    ]
    return {target: mocker.patch(target, return_value=None) for target in targets}
