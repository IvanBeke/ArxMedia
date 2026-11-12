from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control
from django.views.static import serve

from web.views import SPAView


def healthcheck(_request):
    return JsonResponse({'status': 'ok'})


# Only avatars are public; imports and exports under MEDIA_ROOT stay private.
# Each upload gets a new URL, so the files can be cached indefinitely.
@cache_control(public=True, max_age=60 * 60 * 24 * 365, immutable=True)
def serve_avatar(request, path):
    return serve(request, path, document_root=str(Path(settings.MEDIA_ROOT) / 'avatars'))

urlpatterns = [
    path('healthz/', healthcheck, name='healthcheck'),
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/media/', include('media.urls')),
    path('api/tracking/', include('tracking.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/social/', include('social.urls')),
    path('api/calendar/', include('my_calendar.urls')),
    path('api/integrations/', include('integrations.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/avatars/(?P<path>.*)$', serve_avatar),
]

urlpatterns += [
    re_path(r'^(?!static/|media/|api/|admin/|healthz/|sw\.js|manifest\.webmanifest).*$', SPAView.as_view(), name='spa-fallback'),
]
