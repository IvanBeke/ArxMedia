from django.urls import path

from . import views

urlpatterns = [
    path('search/', views.search, name='search'),
    path('trending/', views.trending, name='trending'),
    path('popular/', views.popular, name='popular'),
    path('movies/<int:tmdb_id>/', views.movie_detail, name='movie_detail'),
    path('movies/<int:tmdb_id>/credits/', views.movie_credits, name='movie_credits'),
    path('tv/<int:tmdb_id>/', views.tv_detail, name='tv_detail'),
    path('tv/<int:tmdb_id>/credits/', views.tv_credits, name='tv_credits'),
    path('tv/<int:tmdb_id>/seasons/<int:season_number>/', views.season_detail, name='season_detail'),
    path('tv/<int:tmdb_id>/seasons/<int:season_number>/episodes/<int:episode_number>/credits/', views.episode_credits, name='episode_credits'),
]
