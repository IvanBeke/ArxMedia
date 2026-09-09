from django.contrib import admin
from django.db import models

from .models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'tmdb_id']
    search_fields = ['name', 'tmdb_id']
    ordering = ['name']
    fieldsets = (
        ('Genre', {'fields': ('name', 'tmdb_id')}),
    )


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'tmdb_id', 'release_date', 'status', 'language', 'vote_average', 'vote_count',
        'updated_at',
    ]
    search_fields = ['title', 'tagline', 'overview', 'tmdb_id', 'language', 'status']
    list_filter = ['genres', 'status', 'language', 'release_date']
    ordering = ['title']
    readonly_fields = ['created_at', 'updated_at', 'poster_url', 'backdrop_url']
    fieldsets = (
        ('Identity', {'fields': ('title', 'tmdb_id', 'tagline', 'overview')}),
        ('Release and classification', {
            'fields': ('release_date', 'runtime', 'language', 'status', 'genres'),
        }),
        ('Ratings', {'fields': ('vote_average', 'vote_count')}),
        ('Artwork', {'fields': ('poster_path', 'poster_url', 'backdrop_path', 'backdrop_url')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(TVShow)
class TVShowAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'tmdb_id', 'first_air_date', 'last_air_date', 'status',
        'number_of_seasons', 'number_of_episodes', 'vote_average', 'updated_at',
    ]
    search_fields = ['name', 'overview', 'tmdb_id', 'language', 'status', 'networks']
    list_filter = ['genres', 'status', 'language', 'first_air_date', 'last_air_date']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at', 'poster_url', 'backdrop_url']
    fieldsets = (
        ('Identity', {'fields': ('name', 'tmdb_id', 'overview')}),
        ('Broadcast metadata', {
            'fields': (
                'first_air_date', 'last_air_date', 'status', 'language', 'networks',
                'episode_runtime', 'number_of_seasons', 'number_of_episodes',
            ),
        }),
        ('Ratings and genres', {'fields': ('vote_average', 'vote_count', 'genres')}),
        ('Artwork and external IDs', {
            'fields': ('poster_path', 'poster_url', 'backdrop_path', 'backdrop_url', 'external_ids'),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['show', 'season_number', 'episode_count_display']
    search_fields = ['show__name', 'name', 'tmdb_id', 'show__tmdb_id']
    list_filter = ['show']
    ordering = ['show__name', 'season_number']
    list_select_related = ['show']
    fieldsets = (
        ('Season', {'fields': ('show', 'season_number', 'name', 'tmdb_id')}),
        ('Metadata', {'fields': ('overview', 'air_date', 'episode_count_display')}),
        ('Artwork and external IDs', {'fields': ('poster_path', 'poster_url', 'external_ids')}),
    )
    readonly_fields = ['poster_url', 'air_date', 'episode_count_display']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(admin_episode_count=models.Count('episodes'))

    @admin.display(description='Episode count', ordering='admin_episode_count')
    def episode_count_display(self, obj):
        return obj.episode_count


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ['season', 'episode_number', 'name', 'air_date']
    search_fields = [
        'name', 'overview', 'tmdb_id', 'episode_type',
        'season__name', 'season__show__name', 'season__show__tmdb_id',
    ]
    list_filter = ['season__show', 'season', 'episode_type', 'air_date', 'broadcast_start']
    ordering = ['season__show__name', 'season__season_number', 'episode_number']
    list_select_related = ['season', 'season__show']
    fieldsets = (
        ('Episode', {'fields': ('season', 'episode_number', 'name', 'tmdb_id', 'episode_type')}),
        ('Metadata', {'fields': ('overview', 'air_date', 'broadcast_start', 'runtime')}),
        ('Ratings', {'fields': ('vote_average', 'vote_count')}),
        ('Artwork and external IDs', {'fields': ('still_path', 'external_ids')}),
    )


@admin.register(EpisodeCredit)
class EpisodeCreditAdmin(admin.ModelAdmin):
    list_display = ['episode', 'created_at', 'updated_at']
    search_fields = ['episode__name', 'episode__season__show__name', 'episode__tmdb_id']
    list_filter = ['episode__season__show', 'created_at', 'updated_at']
    ordering = ['episode__season__show__name', 'episode__season__season_number', 'episode__episode_number']
    list_select_related = ['episode', 'episode__season', 'episode__season__show']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Episode', {'fields': ('episode',)}),
        ('Credits', {'fields': ('cast', 'crew', 'guest_stars')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
