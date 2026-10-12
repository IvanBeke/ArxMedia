

import pytest
from django.contrib.auth import get_user_model

from media.models import Episode, Season, TVShow
from tracking.models import (
    UserMediaStatus,
    WatchEntry,
)

User = get_user_model()


pytestmark = pytest.mark.django_db

class UserDeletionTests:
    def test_deleting_user_does_not_recreate_tv_status_rows(self, user, user2, tmdb_noop):
        show = TVShow.objects.create(tmdb_id=9400, name='Delete Safe Show', status='Ended')
        season = Season.objects.create(show=show, tmdb_id=94001, season_number=1, name='Season 1')
        Episode.objects.create(season=season, tmdb_id=940011, episode_number=1, name='Ep 1', air_date='2024-01-01')

        WatchEntry.objects.create(
            user=user,
            media_type='episode',
            tmdb_id=9400,
            season_number=1,
            episode_number=1,
        )

        deleted_user_id = user.id
        user.delete()

        assert not User.objects.filter(id=deleted_user_id).exists()
        assert not UserMediaStatus.objects.filter(user_id=deleted_user_id, media_type='tv', tmdb_id=9400).exists()
