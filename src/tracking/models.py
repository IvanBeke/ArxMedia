from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Subquery
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

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


class WatchEntryQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def episodes(self):
        return self.filter(media_type=WatchEntryMediaType.EPISODE)

    def movies(self):
        return self.filter(media_type=WatchEntryMediaType.MOVIE)

    def for_show(self, tmdb_id):
        return self.episodes().filter(tmdb_id=tmdb_id)

    def with_event_at(self):
        return self.annotate(
            event_at=Coalesce(
                'watched_at', 'created_at', output_field=models.DateTimeField()
            )
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
    objects = WatchEntryQuerySet.as_manager()

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


class UserMediaStatusQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def for_media(self, media_type: str):
        return self.filter(media_type=media_type)

    def planning(self):
        return self.filter(status=TvShowStatus.PLAN_TO_WATCH)

    def shows(self):
        return self.filter(media_type=MediaType.TV)

    def movies(self):
        return self.filter(media_type=MediaType.MOVIE)

    def started(self):
        return self.filter(status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED, TvShowStatus.DROPPED))

    def active(self):
        return self.filter(status__in=(TvShowStatus.WATCHING, TvShowStatus.WATCHED))

    def progressable(self):
        return self.active().with_watched_episodes()

    def with_watched_episodes(self):
        from media.models import Episode

        known_episode = Episode.objects.filter(
            season__show__tmdb_id=OuterRef('tmdb_id'),
            season__season_number=OuterRef('season_number'),
            episode_number=OuterRef('episode_number'),
        )
        watched_episode = WatchEntry.objects.filter(
            user_id=OuterRef('user_id'),
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=OuterRef('tmdb_id'),
            season_number__gt=0,
        ).filter(Exists(known_episode))
        return self.annotate(has_watched_episodes=Exists(watched_episode)).filter(has_watched_episodes=True)

    def watching(self):
        return self.filter(status=TvShowStatus.WATCHING)

    def watched(self):
        return self.filter(status=TvShowStatus.WATCHED)

    def dropped(self):
        return self.filter(status=TvShowStatus.DROPPED)

    def with_next_episode(self, now=None):
        from media.models import Episode

        now = now or timezone.now()
        watched_episode = WatchEntry.objects.filter(
            user_id=OuterRef(OuterRef('user_id')),
            media_type=WatchEntryMediaType.EPISODE,
            tmdb_id=OuterRef('season__show__tmdb_id'),
            season_number=OuterRef('season__season_number'),
            episode_number=OuterRef('episode_number'),
        )
        candidates = Episode.objects.filter(
            season__show__tmdb_id=OuterRef('tmdb_id'),
        ).filter(Episode.released_q(now)).filter(~Exists(watched_episode)).annotate(
            schedule_at=Coalesce('broadcast_start', Cast('air_date', output_field=models.DateTimeField())),
        ).order_by('schedule_at', 'season__season_number', 'episode_number', 'id')

        fields = {
            'next_episode_id': 'id',
            'next_season_number': 'season__season_number',
            'next_episode_number': 'episode_number',
            'next_episode_name': 'name',
            'next_still_path': 'still_path',
            'next_air_date': 'air_date',
            'next_broadcast_start': 'broadcast_start',
            'next_runtime': 'runtime',
            'next_episode_type': 'episode_type',
            'next_vote_average': 'vote_average',
            'next_vote_count': 'vote_count',
        }
        return self.annotate(**{
            name: Subquery(candidates.values(field)[:1])
            for name, field in fields.items()
        })


class UserMediaStatusManager(models.Manager.from_queryset(UserMediaStatusQuerySet)):  # type: ignore[misc]
    def set_planning(self, user, media_type: str, tmdb_id: int):
        now = timezone.now()
        defaults = {
            'status': TvShowStatus.PLAN_TO_WATCH,
            'plan_to_watch_at': now,
            'status_changed_at': now,
        }
        obj, _ = self.update_or_create(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
            defaults=defaults,
        )
        return obj

    def clear_planning(self, user, media_type: str, tmdb_id: int):
        self.filter(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
            status=TvShowStatus.PLAN_TO_WATCH,
        ).delete()

    def set_status(self, user, media_type: str, tmdb_id: int, status: str):
        obj, _ = self.update_or_create(
            user=user,
            media_type=media_type,
            tmdb_id=tmdb_id,
            defaults={
                'status': status,
                'status_changed_at': timezone.now(),
            },
        )
        return obj


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
    custom_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        unique_together = ('custom_list', 'media_type', 'tmdb_id')
        ordering = ['custom_order', 'added_at']
        indexes = [
            models.Index(fields=['custom_list', 'custom_order']),
        ]

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


class UserMediaStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='media_statuses')
    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    tmdb_id = models.IntegerField()
    status = models.CharField(max_length=20, choices=TvShowStatus.choices)
    watched_episodes = models.IntegerField(default=0)
    total_episodes = models.IntegerField(default=0)
    progress_percent = models.IntegerField(default=0)
    episodes_left = models.IntegerField(default=0)
    time_left_minutes = models.IntegerField(default=0)
    time_left_has_unknown = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    dropped_at = models.DateTimeField(null=True, blank=True)
    plan_to_watch_at = models.DateTimeField(null=True, blank=True)
    last_watched_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserMediaStatusManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'media_type', 'tmdb_id'], name='uniq_user_media_status_entry'),
            models.CheckConstraint(
                condition=(
                    models.Q(media_type=MediaType.MOVIE, status__in=[
                        TvShowStatus.PLAN_TO_WATCH,
                        TvShowStatus.WATCHED,
                        TvShowStatus.DROPPED,
                    ])
                    | models.Q(media_type=MediaType.TV, status__in=[
                        TvShowStatus.PLAN_TO_WATCH,
                        TvShowStatus.WATCHING,
                        TvShowStatus.WATCHED,
                        TvShowStatus.DROPPED,
                    ])
                ),
                name='media_status_status_matches_media_type',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'media_type', 'status']),
            models.Index(fields=['user', 'updated_at']),
        ]

    def __str__(self):
        return f'{self.user.username} {self.media_type} {self.tmdb_id}: {self.status}'


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
