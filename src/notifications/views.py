from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.authentication import authenticated_user
from media.models import Movie
from tracking.choices import MediaType
from tracking.query_helpers import build_season_map

from .models import Notification
from .serializers import NotificationSerializer


def notification_context(notifications):
    """Serializer context mapping each notification's key to its Movie or Season (with its show)."""
    movie_ids = {item.tmdb_id for item in notifications if item.media_type == MediaType.MOVIE}
    season_map = build_season_map(
        (item.tmdb_id, item.season_number) for item in notifications if item.media_type == MediaType.TV
    )
    media = {(MediaType.MOVIE, movie.tmdb_id, None): movie for movie in Movie.objects.filter(tmdb_id__in=movie_ids)}
    media.update({(MediaType.TV, *key): season for key, season in season_map.items() if season is not None})
    return {'media': media}


class NotificationViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=authenticated_user(self.request))

    def list(self, request, *args, **kwargs):
        items = self.paginate_queryset(self.get_queryset()) or []
        context = dict(self.get_serializer_context())
        context.update(notification_context(items))
        return self.get_paginated_response(self.get_serializer(items, many=True, context=context).data)

    @action(detail=False, url_path='unread-count')
    def unread_count(self, request):
        return Response({'unread_count': self.get_queryset().filter(read=False).count()})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.read = True
        notification.save(update_fields=['read'])
        return Response(status=status.HTTP_204_NO_CONTENT)
