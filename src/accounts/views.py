from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from social.models import Follow

from .privacy import can_view_account_content, get_viewer_relationship
from .serializers import (
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
    permission_classes = [permissions.AllowAny]
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
    permission_classes = [permissions.AllowAny]

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
    permission_classes = [permissions.AllowAny]

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
