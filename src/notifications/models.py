from django.conf import settings
from django.db import models

from tracking.choices import MediaType


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    season_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['user', '-created_at', '-id'], name='notification_user_newest_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(media_type=MediaType.MOVIE, season_number__isnull=True)
                    | models.Q(media_type=MediaType.TV, season_number__isnull=False, season_number__gte=1)
                ),
                name='notification_valid_release',
            ),
            models.UniqueConstraint(
                fields=['user', 'tmdb_id'], condition=models.Q(media_type=MediaType.MOVIE),
                name='notification_unique_movie',
            ),
            models.UniqueConstraint(
                fields=['user', 'tmdb_id', 'season_number'], condition=models.Q(media_type=MediaType.TV),
                name='notification_unique_season',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} - {self.media_type} {self.tmdb_id} release'
