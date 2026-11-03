from django.urls import path

from . import views

urlpatterns = [
    path('radarr/options/', views.radarr_options, name='radarr_options'),
    path('radarr/movies/<int:tmdb_id>/', views.radarr_movie, name='radarr_movie'),
    path('sonarr/options/', views.sonarr_options, name='sonarr_options'),
    path('sonarr/tv/<int:tmdb_id>/', views.sonarr_series, name='sonarr_series'),
    path('jellyfin/tv/<int:tmdb_id>/links/', views.jellyfin_show_links, name='jellyfin_show_links'),
    path('jellyfin/movies/<int:tmdb_id>/link/', views.jellyfin_movie_link, name='jellyfin_movie_link'),
    path('jellyfin/episodes/links/', views.jellyfin_episode_links, name='jellyfin_episode_links'),
]
