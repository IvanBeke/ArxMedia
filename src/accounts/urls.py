from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', views.RefreshTokenView.as_view(), name='token_refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('users/<str:username>/', views.UserProfileView.as_view(), name='user_profile'),
    path('users/<str:username>/follow/', views.FollowView.as_view(), name='follow'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password_change'),
]
