from rest_framework import serializers

from .models import Episode, Genre, Movie, Season, TVShow


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'tmdb_id', 'name']


class MovieSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    poster_url = serializers.ReadOnlyField()
    backdrop_url = serializers.ReadOnlyField()
    metadata_updated_at = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Movie
        fields = [
            'id', 'tmdb_id', 'title', 'overview', 'poster_path', 'backdrop_path',
            'poster_url', 'backdrop_url', 'release_date', 'runtime',
            'vote_average', 'vote_count', 'genres', 'language', 'tagline', 'status', 'metadata_updated_at'
        ]


class TVShowSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    poster_url = serializers.ReadOnlyField()
    backdrop_url = serializers.ReadOnlyField()
    metadata_updated_at = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = TVShow
        fields = [
            'id', 'tmdb_id', 'name', 'overview', 'poster_path', 'backdrop_path',
            'poster_url', 'backdrop_url', 'first_air_date', 'last_air_date',
            'number_of_seasons', 'number_of_episodes', 'vote_average', 'vote_count',
            'genres', 'language', 'status', 'networks', 'episode_runtime', 'metadata_updated_at'
        ]


class EpisodeSerializer(serializers.ModelSerializer):
    still_url = serializers.ReadOnlyField()
    guest_stars = serializers.SerializerMethodField()
    crew = serializers.SerializerMethodField()

    class Meta:
        model = Episode
        fields = [
            'id', 'tmdb_id', 'episode_number', 'name', 'overview',
            'still_path', 'still_url', 'air_date', 'runtime', 
            'vote_average', 'vote_count', 'episode_type', 'guest_stars', 'crew'
        ]

    def get_guest_stars(self, obj):
        credits = getattr(obj, 'credits', None)
        if credits:
            return credits.guest_stars
        return []

    def get_crew(self, obj):
        credits = getattr(obj, 'credits', None)
        if credits:
            return credits.crew
        return []


class SeasonBriefSerializer(serializers.ModelSerializer):
    poster_url = serializers.ReadOnlyField()
    episode_count = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = ['id', 'season_number', 'name', 'poster_path', 'poster_url', 'air_date', 'episode_count']

    def get_episode_count(self, obj):
        if hasattr(obj, 'actual_episode_count'):
            return obj.actual_episode_count
        return obj.episodes.count()


class SeasonSerializer(serializers.ModelSerializer):
    episodes = serializers.SerializerMethodField()
    poster_url = serializers.ReadOnlyField()
    episode_count = serializers.SerializerMethodField()

    class Meta:
        model = Season
        fields = [
            'id', 'tmdb_id', 'season_number', 'name', 'overview',
            'poster_path', 'poster_url', 'air_date', 'episode_count', 'episodes'
        ]

    def get_episode_count(self, obj):
        if hasattr(obj, 'actual_episode_count'):
            return obj.actual_episode_count
        return obj.episodes.count()

    def get_episodes(self, obj):
        qs = obj.episodes.order_by('episode_number')
        return EpisodeSerializer(qs, many=True).data
