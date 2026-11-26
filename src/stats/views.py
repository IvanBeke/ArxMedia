from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.privacy import can_view_account_content, get_viewer_relationship

from .entries import MAX_YEAR, MIN_YEAR
from .habits import habits_stats
from .library import library_stats
from .monthly import monthly_stats
from .ratings import rating_stats
from .watch_count import watch_count_stats
from .watch_time import watch_time_stats
from .years import years_stats

User = get_user_model()


class StatsViewSet(viewsets.ViewSet):
    """One action per section of a profile's stats page, at `/api/stats/<username>/<action>/`."""

    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'username'
    lookup_value_regex = '[^/]+'

    def _stats_for(self, request, username, compute):
        """Answer `compute(user_id)` if the viewer may see the profile's content, as the other profile sections do."""
        target = get_object_or_404(User, username=username)
        relationship = get_viewer_relationship(request.user, target)
        if not can_view_account_content(target.account_visibility, relationship):
            raise PermissionDenied(_('You do not have permission to view stats for this profile.'))

        return Response(compute(target.id))

    @staticmethod
    def _year(request):
        """The optional `year` query parameter, or None when absent."""
        value = request.query_params.get('year')
        if value is None:
            return None
        if not value.isdecimal() or not MIN_YEAR <= int(value) <= MAX_YEAR:
            message = _('Year must be a whole number between %(min)s and %(max)s.') % {'min': MIN_YEAR, 'max': MAX_YEAR}
            raise ValidationError({'year': [message]})
        return int(value)

    @action(detail=True)
    def ratings(self, request, username):
        return self._stats_for(request, username, rating_stats)

    @action(detail=True)
    def library(self, request, username):
        return self._stats_for(request, username, library_stats)

    @action(detail=True, url_path='watch-count')
    def watch_count(self, request, username):
        return self._stats_for(request, username, watch_count_stats)

    @action(detail=True, url_path='watch-time')
    def watch_time(self, request, username):
        return self._stats_for(request, username, watch_time_stats)

    @action(detail=True)
    def monthly(self, request, username):
        return self._stats_for(request, username, lambda user_id: monthly_stats(user_id, self._year(request)))

    @action(detail=True)
    def years(self, request, username):
        return self._stats_for(request, username, years_stats)

    @action(detail=True)
    def habits(self, request, username):
        return self._stats_for(request, username, habits_stats)
