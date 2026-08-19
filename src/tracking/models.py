from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .choices import (
    DataImportMode,
    DataTransferFormat,
    DataTransferJobType,
    DataTransferSource,
    DataTransferStatus,
    ListPrivacy,
    MediaType,
    TvShowStatus,
    WatchEntryMediaType,
)


class WatchEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watchentries'
    )
    media_type = models.CharField(max_length=10, choices=WatchEntryMediaType.choices)
    tmdb_id = models.IntegerField()
    watched_at = models.DateTimeField(null=True, blank=True)
    season_number = models.IntegerField(null=True, blank=True)
    episode_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'media_type', 'tmdb_id']),
            models.Index(fields=['user', 'media_type', 'tmdb_id', 'season_number', 'episode_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'media_type', 'tmdb_id'],
                condition=models.Q(media_type=WatchEntryMediaType.MOVIE),
                name='unique_user_movie_tmdb'
            ),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.media_type} {self.tmdb_id}'


class Rating(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings'
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'media_type', 'tmdb_id')
        indexes = [
            models.Index(fields=['user', 'updated_at']),
        ]

    def __str__(self):
        return f'{self.user.username} rated {self.media_type} {self.tmdb_id}: {self.score}/10'


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watchlist_entries'
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    notes = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'media_type', 'tmdb_id')
        indexes = [
            models.Index(fields=['user', 'added_at']),
        ]

    def __str__(self):
        return f'{self.user.username} watchlist: {self.media_type} {self.tmdb_id}'


class Review(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews'
    )
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    content = models.TextField()
    contains_spoilers = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'media_type', 'tmdb_id')
        indexes = [
            models.Index(fields=['media_type', 'tmdb_id', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} review for {self.media_type} {self.tmdb_id}'


class CustomList(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='custom_lists'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    privacy = models.CharField(max_length=20, choices=ListPrivacy.choices, default=ListPrivacy.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.name}'


class ListItem(models.Model):
    custom_list = models.ForeignKey(CustomList, on_delete=models.CASCADE, related_name='items')
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('custom_list', 'media_type', 'tmdb_id')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.custom_list.name} - {self.media_type} {self.tmdb_id}'


class ListCollaborator(models.Model):
    custom_list = models.ForeignKey(CustomList, on_delete=models.CASCADE, related_name='collaboratorships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='list_collaborations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('custom_list', 'user')

    def __str__(self):
        return f'{self.custom_list.name} collaborator: {self.user.username}'


class UserTvShowStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tv_show_statuses')
    tmdb_id = models.IntegerField()
    status = models.CharField(max_length=20, choices=TvShowStatus.choices, default=TvShowStatus.NONE)
    watched_episodes = models.IntegerField(default=0)
    total_episodes = models.IntegerField(default=0)
    progress_percent = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    plan_to_watch_at = models.DateTimeField(null=True, blank=True)
    last_watched_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'tmdb_id')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'updated_at']),
        ]

    def __str__(self):
        return f'{self.user.username} TV {self.tmdb_id}: {self.status}'


class DataTransferJob(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='data_jobs')
    job_type = models.CharField(max_length=10, choices=DataTransferJobType.choices)
    data_format = models.CharField(max_length=10, choices=DataTransferFormat.choices)
    status = models.CharField(max_length=32, choices=DataTransferStatus.choices, default=DataTransferStatus.PENDING)
    input_file = models.FileField(upload_to='imports/', null=True, blank=True)
    output_file = models.FileField(upload_to='exports/', null=True, blank=True)
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=DataTransferSource.choices, default=DataTransferSource.ARXMEDIA)
    import_mode = models.CharField(max_length=32, choices=DataImportMode.choices, default=DataImportMode.NEW_ITEMS)
    overwrite_existing = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'status', 'created_at']),
        ]

    def __str__(self):
        return f'Job {self.id} {self.job_type}/{self.data_format} {self.status}'
