from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Avg, Count, Q
from rest_framework import serializers
from tracking.choices import ListPrivacy
from tracking.models import CustomList, Rating, WatchEntry, Watchlist
from tracking.serializers import CustomListSerializer, WatchEntrySerializer

from .privacy import can_view_account_content, get_viewer_relationship

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    total_watched_movies = serializers.ReadOnlyField()
    total_watched_episodes = serializers.ReadOnlyField()
    preferred_region = serializers.CharField(max_length=2)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'bio', 'avatar', 'location',
            'website', 'preferred_region', 'account_visibility', 'followers_count', 'following_count',
            'total_watched_movies', 'total_watched_episodes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_preferred_region(self, value):
        region = (value or '').strip().upper()
        if len(region) != 2 or not region.isalpha():
            raise serializers.ValidationError('preferred_region must be a 2-letter country code.')
        return region


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class PublicUserSerializer(serializers.ModelSerializer):
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()
    total_watched_movies = serializers.ReadOnlyField()
    total_watched_episodes = serializers.ReadOnlyField()
    viewer_relationship = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    visible_lists = serializers.SerializerMethodField()
    recent_activity = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'bio', 'avatar', 'location',
            'account_visibility',
            'followers_count', 'following_count',
            'total_watched_movies', 'total_watched_episodes', 'created_at',
            'viewer_relationship', 'permissions', 'stats', 'visible_lists', 'recent_activity'
        ]

    def _viewer_relationship(self, obj):
        if not hasattr(self, '_relationship_cache'):
            self._relationship_cache = {}

        if obj.id not in self._relationship_cache:
            request = self.context.get('request')
            viewer = getattr(request, 'user', None)
            self._relationship_cache[obj.id] = get_viewer_relationship(viewer, obj)

        return self._relationship_cache[obj.id]

    def _can_view(self, obj):
        if not hasattr(self, '_can_view_cache'):
            self._can_view_cache = {}

        if obj.id not in self._can_view_cache:
            relationship = self._viewer_relationship(obj)
            self._can_view_cache[obj.id] = can_view_account_content(obj.account_visibility, relationship)

        return self._can_view_cache[obj.id]

    def get_viewer_relationship(self, obj):
        return self._viewer_relationship(obj)

    def get_permissions(self, obj):
        can_view = self._can_view(obj)
        return {
            'can_view_activity': can_view,
            'can_view_lists': can_view,
        }

    def get_stats(self, obj):
        if not self._can_view(obj):
            return {
                'ratings_count': None,
                'watchlist_count': None,
                'average_rating': None,
            }

        ratings_summary = Rating.objects.filter(user=obj).aggregate(
            ratings_count=Count('id'),
            average_rating=Avg('score'),
        )
        watchlist_count = Watchlist.objects.filter(user=obj).count()
        avg_rating = ratings_summary['average_rating']

        return {
            'ratings_count': ratings_summary['ratings_count'],
            'watchlist_count': watchlist_count,
            'average_rating': round(avg_rating, 1) if avg_rating else None,
        }

    def get_visible_lists(self, obj):
        if not self._can_view(obj):
            return []

        relationship = self._viewer_relationship(obj)
        qs = CustomList.objects.filter(user=obj)
        if relationship['is_self']:
            return CustomListSerializer(qs.order_by('-updated_at'), many=True).data

        request = self.context.get('request')
        viewer = getattr(request, 'user', None)
        qs = qs.filter(
            Q(privacy=ListPrivacy.PUBLIC)
            | Q(privacy=ListPrivacy.PRIVATE, collaboratorships__user=viewer)
        ).distinct()

        return CustomListSerializer(qs.order_by('-updated_at'), many=True).data

    def get_recent_activity(self, obj):
        if not self._can_view(obj):
            return []

        entries = list(
            WatchEntry.objects.filter(user=obj)
            .order_by('-watched_at', '-id')[:12]
        )
        if not entries:
            return []

        movie_ids = [entry.tmdb_id for entry in entries if entry.media_type == 'movie']
        tv_ids = [entry.tmdb_id for entry in entries if entry.media_type == 'episode']

        from media.models import Movie, TVShow

        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=tv_ids)}

        return WatchEntrySerializer(entries, many=True, context={'movie_map': movie_map, 'tv_map': tv_map}).data


class PublicUserCardSerializer(serializers.ModelSerializer):
    followers_count = serializers.ReadOnlyField()
    following_count = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'username', 'bio', 'avatar', 'followers_count', 'following_count']


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
