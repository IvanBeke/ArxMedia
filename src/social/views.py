from accounts.privacy import visible_owner_q
from django.contrib.auth import get_user_model
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from tracking.models import WatchEntry
from tracking.query_helpers import watch_entry_context
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

    entries = list(
        WatchEntry.objects.filter(
            visible_owner_q(request.user),
            user_id__in=following_ids,
        ).select_related('user').order_by('-watched_at')[:50]
    )

    data = WatchEntrySerializer(entries, many=True, context=watch_entry_context(entries)).data
    for row, entry in zip(data, entries):
        row['username'] = entry.user.username

    return Response(data)
