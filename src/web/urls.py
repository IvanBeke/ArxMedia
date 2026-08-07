from django.urls import path

from .views import SPAView


urlpatterns = [
    path('', SPAView.as_view(), name='spa'),
]
