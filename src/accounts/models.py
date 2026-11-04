from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import get_random_string

from tracking.choices import WatchEntryMediaType


def avatar_upload_path(instance, filename):
    # A fresh random suffix per upload gives every avatar a new URL, so browsers never serve a stale one.
    return f'avatars/{instance.username}_{get_random_string(8)}.webp'


class AccountVisibility(models.TextChoices):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'
    FRIENDS_ONLY = 'friends_only', 'Friends only'


class User(AbstractUser):
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, null=True, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    preferred_region = models.CharField(max_length=2, default='US')
    account_visibility = models.CharField(max_length=20, choices=AccountVisibility.choices, default=AccountVisibility.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(AbstractUser.Meta):
        permissions = [
            ('use_sonarr_radarr', 'Can add media to Sonarr and Radarr'),
            ('use_jellyfin', 'Can open media in Jellyfin'),
        ]

    def __str__(self):
        return self.username

    @property
    def followers_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()

    @property
    def total_watched_movies(self):
        return self.watchentries.filter(
            media_type=WatchEntryMediaType.MOVIE,
        ).count()

    @property
    def total_watched_episodes(self):
        return self.watchentries.filter(
            media_type=WatchEntryMediaType.EPISODE,
        ).count()
