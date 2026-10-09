from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from media.models import Movie, TVShow
from social.models import Follow
from tracking.models import WatchEntry, WatchEntryMediaType

from .authentication import authenticated_user
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


# DRF only enforces CSRF for authenticated sessions; these views also need it
# for anonymous requests to prevent login CSRF.
@method_decorator(csrf_protect, name='dispatch')
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        login(request, user)
        return Response(UserSerializer(user).data)


@method_decorator(csrf_protect, name='dispatch')
class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        user = authenticated_user(self.request)
        return User.objects.filter(username__icontains=query).exclude(id=user.id).order_by('username')[:10]


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
        user = serializer.save()
        update_session_auth_hash(request, user)
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

        # A timestamp range on watched_at lets Postgres read just this window from the index;
        # entries with an unknown watch date (null) have no day, so they are left out.
        tz = timezone.get_current_timezone()
        window_start = timezone.make_aware(datetime.combine(start, time.min), tz)
        window_end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
        rows = list(
            WatchEntry.objects
            .filter(user=target)
            .filter(watched_at__gte=window_start, watched_at__lt=window_end)
            .annotate(day=TruncDate('watched_at'))
            .values('day', 'media_type', 'tmdb_id', 'season_number', 'episode_number')
            .order_by('day', 'id')
        )
        movie_ids = {row['tmdb_id'] for row in rows if row['media_type'] == WatchEntryMediaType.MOVIE}
        show_ids = {row['tmdb_id'] for row in rows if row['media_type'] != WatchEntryMediaType.MOVIE}
        movies = {
            tmdb_id: (title, release_date)
            for tmdb_id, title, release_date in Movie.objects.filter(tmdb_id__in=movie_ids)
            .values_list('tmdb_id', 'title', 'release_date')
        }
        show_names = dict(TVShow.objects.filter(tmdb_id__in=show_ids).values_list('tmdb_id', 'name'))

        items_by_day: dict[date, list[dict]] = {}
        for row in rows:
            if row['media_type'] == WatchEntryMediaType.MOVIE:
                movie_title, release_date = movies.get(row['tmdb_id'], (None, None))
                item = {
                    'media_type': 'movie',
                    'tmdb_id': row['tmdb_id'],
                    'title': movie_title or f"Movie #{row['tmdb_id']}",
                    'release_year': release_date.year if release_date else None,
                }
            else:
                season = row['season_number']
                episode = row['episode_number']
                item = {
                    'media_type': 'episode',
                    'tmdb_id': row['tmdb_id'],
                    'title': show_names.get(row['tmdb_id']) or f"TV #{row['tmdb_id']}",
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
