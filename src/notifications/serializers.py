from django.utils import timezone
from rest_framework import serializers

from tracking.choices import MediaType

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    release_date = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'media_type', 'tmdb_id', 'season_number', 'created_at', 'read',
            'title', 'poster_url', 'release_date',
        ]

    def _media(self, obj):
        """The Movie, or the Season (with its show), this notification points at; None when not stored locally."""
        return self.context['media'].get((obj.media_type, obj.tmdb_id, obj.season_number))

    def get_title(self, obj):
        media = self._media(obj)
        if media is None:
            return ''
        return media.title if obj.media_type == MediaType.MOVIE else media.show.name

    def get_poster_url(self, obj):
        media = self._media(obj)
        if media is None:
            return None
        if obj.media_type == MediaType.MOVIE:
            return media.poster_url
        return media.poster_url or media.show.poster_url

    def get_release_date(self, obj):
        # The daily sweep only announces that day's releases, so the creation day is the release day.
        return timezone.localdate(obj.created_at)
