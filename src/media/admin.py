from django.contrib import admin

from .models import Episode, Genre, Movie, Season, TVShow


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'tmdb_id']


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'tmdb_id', 'release_date', 'vote_average']
    search_fields = ['title']
    list_filter = ['genres']


@admin.register(TVShow)
class TVShowAdmin(admin.ModelAdmin):
    list_display = ['name', 'tmdb_id', 'first_air_date', 'status', 'vote_average']
    search_fields = ['name']


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['show', 'season_number', 'episode_count']


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ['season', 'episode_number', 'name', 'air_date']
