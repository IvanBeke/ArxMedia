from django.urls import path

from . import views


urlpatterns = [
    path('shows/', views.shows_calendar, name='calendar_shows'),
    path('movies/', views.movies_calendar, name='calendar_movies'),
    path('my/', views.my_calendar, name='calendar_my'),
]
