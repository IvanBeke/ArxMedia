from django.urls import path

from . import views

urlpatterns = [
    path('radarr/options/', views.radarr_options, name='radarr_options'),
    path('radarr/movies/<int:tmdb_id>/', views.radarr_movie, name='radarr_movie'),
]
