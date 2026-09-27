from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import DateTimeField, OuterRef, Subquery
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from media.models import Movie, TVShow
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from social.models import Follow
from tracking.models import WatchEntry, WatchEntryMediaType

from .privacy import can_view_account_content, get_viewer_relationship
from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PublicUserCardSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_register'


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_login'


class RefreshTokenView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_refresh'


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = PublicUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all()
    lookup_field = 'username'


class UserSearchView(generics.ListAPIView):
    serializer_class = PublicUserCardSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        query = (self.request.query_params.get('q') or '').strip()
        if len(query) < 3:
            return User.objects.none()

        return User.objects.filter(username__icontains=query).exclude(id=self.request.user.id).order_by('username')[:10]


class UserFollowersView(generics.ListAPIView):
    serializer_class = PublicUserCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _target(self):
        return get_object_or_404(User, username=self.kwargs['username'])

    def get_queryset(self):
        target = self._target()

        relationship = get_viewer_relationship(self.request.user, target)
        if not can_view_account_content(target.account_visibility, relationship):
            raise PermissionDenied('You do not have permission to view followers for this profile.')

        return User.objects.filter(following__following=target).order_by('username')


class UserFollowingView(generics.ListAPIView):
    serializer_class = PublicUserCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _target(self):
        return get_object_or_404(User, username=self.kwargs['username'])

    def get_queryset(self):
        target = self._target()

        relationship = get_viewer_relationship(self.request.user, target)
        if not can_view_account_content(target.account_visibility, relationship):
            raise PermissionDenied('You do not have permission to view following for this profile.')

        return User.objects.filter(followers__follower=target).order_by('username')


class FollowView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, username):
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target == request.user:
            return Response({'detail': 'Cannot follow yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if not created:
            follow.delete()
            following = False
        else:
            following = True

        target_follows_viewer = Follow.objects.filter(follower=target, following=request.user).exists()

        return Response({
            'following': following,
            'is_friend': following and target_follows_viewer,
            'followers_count': target.followers.count(),
            'following_count': target.following.count(),
        })


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)


class UserActivityHeatmapView(APIView):
    """Daily watch-activity counts for a profile, GitHub-contribution style."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, username):
        target = get_object_or_404(User, username=username)
        relationship = get_viewer_relationship(request.user, target)
        if not can_view_account_content(target.account_visibility, relationship):
            return Response({'days': [], 'total': 0})

        today = timezone.localdate()
        try:
            start = today.replace(year=today.year - 1)
        except ValueError:
            # Today is Feb 29 and last year is not a leap year.
            start = today.replace(year=today.year - 1, day=28)

        # Single query: flat rows annotated with the movie/show display fields,
        # grouped per day in Python.
        rows = (
            WatchEntry.objects
            .filter(user=target)
            .annotate(event_at=Coalesce('watched_at', 'created_at', output_field=DateTimeField()))
            .filter(event_at__date__gte=start, event_at__date__lte=today)
            .annotate(
                day=TruncDate('event_at'),
                movie_title=Subquery(
                    Movie.objects.filter(tmdb_id=OuterRef('tmdb_id')).values('title')[:1]
                ),
                movie_release_date=Subquery(
                    Movie.objects.filter(tmdb_id=OuterRef('tmdb_id')).values('release_date')[:1]
                ),
                show_name=Subquery(
                    TVShow.objects.filter(tmdb_id=OuterRef('tmdb_id')).values('name')[:1]
                ),
            )
            .values(
                'day', 'media_type', 'tmdb_id', 'season_number', 'episode_number',
                'movie_title', 'movie_release_date', 'show_name',
            )
            .order_by('day', 'id')
        )

        items_by_day: dict[date, list[dict]] = {}
        for row in rows:
            if row['media_type'] == WatchEntryMediaType.MOVIE:
                release_date = row['movie_release_date']
                item = {
                    'media_type': 'movie',
                    'tmdb_id': row['tmdb_id'],
                    'title': row['movie_title'] or f"Movie #{row['tmdb_id']}",
                    'release_year': release_date.year if release_date else None,
                }
            else:
                season = row['season_number']
                episode = row['episode_number']
                item = {
                    'media_type': 'episode',
                    'tmdb_id': row['tmdb_id'],
                    'title': row['show_name'] or f"TV #{row['tmdb_id']}",
                    'season_number': season,
                    'episode_number': episode,
                    'episode_code': f"S{int(season or 0):02d}E{int(episode or 0):02d}",
                }
            items_by_day.setdefault(row['day'], []).append(item)

        days = []
        total = 0
        for offset in range((today - start).days + 1):
            day = start + timedelta(days=offset)
            items = items_by_day.get(day, [])
            total += len(items)
            days.append({
                'date': day.isoformat(),
                'count': len(items),
                'items': items,
            })

        return Response({'days': days, 'total': total})
