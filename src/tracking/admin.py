from django.contrib import admin

from .models import (
    DataTransferJob,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)


@admin.register(WatchEntry)
class WatchEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'watched_at']
    list_filter = ['media_type']
    search_fields = ['user__username']


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'score', 'updated_at']
    list_filter = ['media_type']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'contains_spoilers', 'created_at']


@admin.register(UserMediaStatus)
class UserMediaStatusAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'media_type',
        'tmdb_id',
        'status',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
        'updated_at',
    ]
    list_filter = ['media_type', 'status']
    search_fields = ['user__username', 'tmdb_id']
    ordering = ['-updated_at']
    readonly_fields = [
        'started_at',
        'completed_at',
        'dropped_at',
        'last_watched_at',
        'status_changed_at',
        'created_at',
        'updated_at',
    ]


@admin.register(DataTransferJob)
class DataTransferJobAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'job_type',
        'source',
        'data_format',
        'status',
        'import_mode',
        'processed_items',
        'total_items',
        'updated_at',
    ]
    list_filter = ['job_type', 'source', 'data_format', 'status', 'import_mode']
    search_fields = ['id', 'user__username', 'error_message']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
