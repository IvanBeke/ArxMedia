from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from web.views import SPAView


def healthcheck(_request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('healthz/', healthcheck, name='healthcheck'),
    path('', SPAView.as_view(), name='spa-root'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/media/', include('media.urls')),
    path('api/tracking/', include('tracking.urls')),
    path('api/social/', include('social.urls')),
    path('api/calendar/', include('my_calendar.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path('<path:path>', SPAView.as_view(), name='spa-fallback'),
]
