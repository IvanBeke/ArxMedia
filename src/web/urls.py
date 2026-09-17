from django.urls import path

from .views import ManifestView, ServiceWorkerView, SPAView

urlpatterns = [
    path('manifest.webmanifest', ManifestView.as_view(), name='pwa-manifest'),
    path('sw.js', ServiceWorkerView.as_view(), name='pwa-service-worker'),
    path('', SPAView.as_view(), name='spa-root'),
]
