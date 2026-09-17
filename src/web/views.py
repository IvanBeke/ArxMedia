import logging
from pathlib import Path

from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.views import View
from django.views.generic import TemplateView

logger = logging.getLogger(__name__)

PWA_MANIFEST = {
    'name': 'ArxMedia - Track What You Watch',
    'short_name': 'ArxMedia',
    'description': 'Track movies and shows you watch.',
    'start_url': '/',
    'scope': '/',
    'display': 'standalone',
    'orientation': 'portrait-primary',
    'background_color': '#1a1a1a',
    'theme_color': '#9f42c6',
    'icons': [
        {'src': '/static/web/pwa-192.png', 'sizes': '192x192', 'type': 'image/png'},
        {'src': '/static/web/pwa-512.png', 'sizes': '512x512', 'type': 'image/png'},
        {
            'src': '/static/web/maskable-512.png',
            'sizes': '512x512',
            'type': 'image/png',
            'purpose': 'maskable',
        },
    ],
}


class SPAView(TemplateView):
    template_name = 'web/index.html'


class ManifestView(View):
    """Serve the PWA web manifest at root scope for installability."""

    def get(self, request: HttpRequest) -> HttpResponse:
        response = JsonResponse(PWA_MANIFEST)
        response['Cache-Control'] = 'public, max-age=86400'
        return response


def resolve_service_worker_path() -> Path | None:
    """Locate the Vite-built service worker so it can be served at root scope.

    A worker served under /static/web/ would be scoped to that prefix and could
    not intercept app navigations, so Django serves the built file at /sw.js.
    Returns None when the UI has not been built yet (e.g. fresh dev checkout).
    """
    found = finders.find('web/sw.js')
    return Path(found) if found else None


class ServiceWorkerView(View):
    """Serve the generated service worker at /sw.js with root scope allowed."""

    def get(self, request: HttpRequest) -> HttpResponse | FileResponse:
        path = resolve_service_worker_path()
        if path is None:
            logger.debug('Service worker requested before UI build; returning 404')
            raise Http404('Service worker not built yet')
        response = FileResponse(path.open('rb'), content_type='application/javascript')
        response['Cache-Control'] = 'no-cache'
        response['Service-Worker-Allowed'] = '/'
        return response
