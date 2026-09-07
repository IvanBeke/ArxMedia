from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve
from web.views import SPAView


def healthcheck(_request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('healthz/', healthcheck, name='healthcheck'),
    path('', include('web.urls')),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/media/', include('media.urls')),
    path('api/tracking/', include('tracking.urls')),
    path('api/social/', include('social.urls')),
    path('api/calendar/', include('my_calendar.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

urlpatterns += [
    re_path(r'^(?!static/|media/|api/|admin/|healthz/).*$', SPAView.as_view(), name='spa-fallback'),
]
