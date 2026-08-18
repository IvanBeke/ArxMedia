from django.contrib import admin

from .models import (
    Rating,
    Review,
    UserSeasonStatus,
    UserTvShowStatus,
    WatchEntry,
    Watchlist,
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


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'added_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'contains_spoilers', 'created_at']


@admin.register(UserTvShowStatus)
class UserTvShowStatusAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'tmdb_id',
        'status',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
        'updated_at',
    ]
    list_filter = ['status']
    search_fields = ['user__username', 'tmdb_id']
    ordering = ['-updated_at']
    readonly_fields = [
        'started_at',
        'completed_at',
        'dropped_at',
        'plan_to_watch_at',
        'last_watched_at',
        'status_changed_at',
        'created_at',
        'updated_at',
    ]


@admin.register(UserSeasonStatus)
class UserSeasonStatusAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'tmdb_id',
        'season_number',
        'status',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
        'updated_at',
    ]
    list_filter = ['status', 'season_number']
    search_fields = ['user__username', 'tmdb_id']
    ordering = ['-updated_at']
    readonly_fields = [
        'started_at',
        'completed_at',
        'last_watched_at',
        'status_changed_at',
        'created_at',
        'updated_at',
    ]
