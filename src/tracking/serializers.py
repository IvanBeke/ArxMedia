from rest_framework import serializers

from .choices import MediaType, WatchEntryMediaType
from .models import CustomList, DataTransferJob, ListCollaborator, ListItem, Rating, Review, WatchEntry, Watchlist


class WatchEntrySerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    poster_path = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    vote_average = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    show_name = serializers.SerializerMethodField()

    class Meta:
        model = WatchEntry
        fields = [
            'id', 'media_type', 'tmdb_id', 'status', 'watched_at',
            'season_number', 'episode_number', 'created_at', 'title', 'poster_path',
            'poster_url', 'vote_average', 'year', 'show_name'
        ]
        read_only_fields = ['id', 'created_at']

    def _get_media(self, obj):
        movie_map = self.context.get('movie_map') or {}
        tv_map = self.context.get('tv_map') or {}

        if obj.media_type == WatchEntryMediaType.MOVIE and obj.tmdb_id in movie_map:
            return movie_map[obj.tmdb_id]
        if obj.media_type == WatchEntryMediaType.EPISODE and obj.tmdb_id in tv_map:
            return tv_map[obj.tmdb_id]

        if obj.media_type == WatchEntryMediaType.MOVIE:
            from media.models import Movie
            return Movie.objects.filter(tmdb_id=obj.tmdb_id).first()
        if obj.media_type == WatchEntryMediaType.EPISODE:
            from media.models import TVShow
            return TVShow.objects.filter(tmdb_id=obj.tmdb_id).first()
        return None

    def get_title(self, obj):
        if obj.media_type == WatchEntryMediaType.EPISODE:
            from media.models import Episode, Season

            if obj.season_number and obj.episode_number:
                season = Season.objects.filter(
                    show__tmdb_id=obj.tmdb_id,
                    season_number=obj.season_number,
                ).first()
                if season:
                    episode = Episode.objects.filter(season=season, episode_number=obj.episode_number).first()
                    if episode and episode.name:
                        return episode.name

            if obj.episode_number:
                return f'Episode {obj.episode_number}'
            return f'Episode #{obj.tmdb_id}'
        media = self._get_media(obj)
        if media:
            if hasattr(media, 'title'):
                return media.title
            return media.name
        return None

    def get_poster_path(self, obj):
        if obj.media_type == WatchEntryMediaType.EPISODE:
            show = self._get_media(obj)
            return show.poster_path if show else None
        media = self._get_media(obj)
        return media.poster_path if media else None

    def get_poster_url(self, obj):
        if obj.media_type == WatchEntryMediaType.EPISODE:
            show = self._get_media(obj)
            return show.poster_url if show else None
        media = self._get_media(obj)
        return media.poster_url if media else None

    def get_vote_average(self, obj):
        if obj.media_type == WatchEntryMediaType.EPISODE:
            show = self._get_media(obj)
            return show.vote_average if show else None
        media = self._get_media(obj)
        return media.vote_average if media else None

    def get_year(self, obj):
        if obj.media_type == WatchEntryMediaType.MOVIE:
            media = self._get_media(obj)
            if media and media.release_date:
                return str(media.release_date)[:4]
            return None
        return None

    def get_show_name(self, obj):
        if obj.media_type == WatchEntryMediaType.EPISODE:
            show = self._get_media(obj)
            return show.name if show else None
        return None


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['id', 'media_type', 'tmdb_id', 'score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class WatchlistSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    poster_path = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    vote_average = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    release_date = serializers.SerializerMethodField()
    first_air_date = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()

    class Meta:
        model = Watchlist
        fields = [
            'id', 'media_type', 'tmdb_id', 'title', 'poster_path', 'poster_url', 'vote_average', 'year',
            'release_date', 'first_air_date', 'user_status', 'notes', 'added_at'
        ]
        read_only_fields = ['id', 'added_at']

    def _get_media(self, obj):
        movie_map = self.context.get('movie_map') or {}
        tv_map = self.context.get('tv_map') or {}
        if obj.media_type == MediaType.MOVIE and obj.tmdb_id in movie_map:
            return movie_map[obj.tmdb_id]
        if obj.media_type == MediaType.TV and obj.tmdb_id in tv_map:
            return tv_map[obj.tmdb_id]

        from media.models import Movie, TVShow
        if obj.media_type == MediaType.MOVIE:
            return Movie.objects.filter(tmdb_id=obj.tmdb_id).first()
        return TVShow.objects.filter(tmdb_id=obj.tmdb_id).first()

    def get_title(self, obj):
        media = self._get_media(obj)
        if media:
            return getattr(media, 'title' if obj.media_type == MediaType.MOVIE else 'name', '')
        return ''

    def get_poster_path(self, obj):
        media = self._get_media(obj)
        return getattr(media, 'poster_path', '') if media else ''

    def get_poster_url(self, obj):
        media = self._get_media(obj)
        if media and media.poster_path:
            return f'https://image.tmdb.org/t/p/w500{media.poster_path}'
        return None

    def get_vote_average(self, obj):
        media = self._get_media(obj)
        return getattr(media, 'vote_average', 0) if media else 0

    def get_year(self, obj):
        media = self._get_media(obj)
        if media:
            date = getattr(media, 'release_date' if obj.media_type == MediaType.MOVIE else 'first_air_date', None)
            return date.year if date else ''
        return ''

    def get_release_date(self, obj):
        if obj.media_type != MediaType.MOVIE:
            return None
        media = self._get_media(obj)
        return media.release_date if media else None

    def get_first_air_date(self, obj):
        if obj.media_type != MediaType.TV:
            return None
        media = self._get_media(obj)
        return media.first_air_date if media else None

    def get_user_status(self, obj):
        status_map = self.context.get('status_map') or {}
        return status_map.get((obj.media_type, obj.tmdb_id))


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'username', 'media_type', 'tmdb_id',
            'content', 'contains_spoilers', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'username', 'created_at', 'updated_at']


class CustomListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    item_count = serializers.SerializerMethodField()
    collaborators = serializers.SerializerMethodField()
    collaborator_users = serializers.SerializerMethodField()

    class Meta:
        model = CustomList
        fields = ['id', 'username', 'name', 'description', 'privacy', 'item_count', 'collaborators', 'collaborator_users', 'created_at', 'updated_at']
        read_only_fields = ['id', 'username', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_collaborators(self, obj):
        return list(obj.collaboratorships.values_list('user__id', flat=True))

    def get_collaborator_users(self, obj):
        return [
            {'id': row['user__id'], 'username': row['user__username']}
            for row in obj.collaboratorships.values('user__id', 'user__username')
        ]


class ListItemSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    poster_path = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = ListItem
        fields = ['id', 'media_type', 'tmdb_id', 'title', 'poster_path', 'poster_url', 'year', 'added_at']
        read_only_fields = ['id', 'added_at']

    def _get_media(self, obj):
        movie_map = self.context.get('movie_map') or {}
        tv_map = self.context.get('tv_map') or {}
        if obj.media_type == MediaType.MOVIE and obj.tmdb_id in movie_map:
            return movie_map[obj.tmdb_id]
        if obj.media_type == MediaType.TV and obj.tmdb_id in tv_map:
            return tv_map[obj.tmdb_id]

        from media.models import Movie, TVShow
        if obj.media_type == MediaType.MOVIE:
            return Movie.objects.filter(tmdb_id=obj.tmdb_id).first()
        return TVShow.objects.filter(tmdb_id=obj.tmdb_id).first()

    def get_title(self, obj):
        media = self._get_media(obj)
        if media:
            return getattr(media, 'title' if obj.media_type == MediaType.MOVIE else 'name', '')
        return ''

    def get_poster_path(self, obj):
        media = self._get_media(obj)
        return getattr(media, 'poster_path', '') if media else ''

    def get_poster_url(self, obj):
        media = self._get_media(obj)
        if media and media.poster_path:
            return f'https://image.tmdb.org/t/p/w500{media.poster_path}'
        return None

    def get_year(self, obj):
        media = self._get_media(obj)
        if media:
            date = getattr(media, 'release_date' if obj.media_type == MediaType.MOVIE else 'first_air_date', None)
            return date.year if date else ''
        return ''


class ListCollaboratorSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ListCollaborator
        fields = ['id', 'user', 'user_id', 'username', 'created_at']


class DataTransferJobSerializer(serializers.ModelSerializer):
    output_url = serializers.SerializerMethodField()

    class Meta:
        model = DataTransferJob
        fields = [
            'id', 'job_type', 'data_format', 'source', 'overwrite_existing', 'status', 'total_items',
            'processed_items', 'error_message', 'output_url', 'metadata', 'created_at', 'updated_at'
        ]

    def get_output_url(self, obj):
        if obj.output_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.output_file.url)
            return obj.output_file.url
        return None
