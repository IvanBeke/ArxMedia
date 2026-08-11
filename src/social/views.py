from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from tracking.choices import WatchEntryStatus
from tracking.models import WatchEntry
from tracking.serializers import WatchEntrySerializer

from .models import Follow

User = get_user_model()


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def activity_feed(request):
    """Get activity feed from followed users."""
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)

    entries = WatchEntry.objects.filter(
        user_id__in=following_ids,
        status=WatchEntryStatus.WATCHED,
    ).select_related('user').order_by('-watched_at')[:50]

    data = []
    for entry in entries:
        d = WatchEntrySerializer(entry).data
        d['username'] = entry.user.username
        data.append(d)

    return Response(data)
