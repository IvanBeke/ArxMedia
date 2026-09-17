"""Tests for PWA root-scope serving (manifest + service worker)."""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase


class ManifestViewTests(TestCase):
    def test_manifest_served_with_installability_fields(self) -> None:
        response = self.client.get('/manifest.webmanifest')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['short_name'], 'ArxMedia')
        self.assertEqual(payload['start_url'], '/')
        self.assertEqual(payload['scope'], '/')
        self.assertEqual(payload['display'], 'standalone')
        self.assertEqual(payload['theme_color'], '#9f42c6')
        sizes = [icon['sizes'] for icon in payload['icons']]
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)
        self.assertTrue(any(icon.get('purpose') == 'maskable' for icon in payload['icons']))
        self.assertEqual(response['Cache-Control'], 'public, max-age=86400')

    def test_manifest_has_json_content_type(self) -> None:
        response = self.client.get('/manifest.webmanifest')

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])


class ServiceWorkerViewTests(TestCase):
    def test_returns_404_when_ui_not_built(self) -> None:
        with mock.patch('web.views.resolve_service_worker_path', return_value=None):
            response = self.client.get('/sw.js')

        self.assertEqual(response.status_code, 404)

    def test_serves_built_worker_with_root_scope_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            worker = Path(tmpdir) / 'sw.js'
            worker.write_text('self.__WB_MANIFEST;')
            with mock.patch('web.views.resolve_service_worker_path', return_value=worker):
                response = self.client.get('/sw.js')

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/javascript')
            self.assertEqual(response['Cache-Control'], 'no-cache')
            self.assertEqual(response['Service-Worker-Allowed'], '/')
            body = b''.join(response.streaming_content)  # type: ignore[attr-defined]
            self.assertEqual(body, b'self.__WB_MANIFEST;')

    def test_sw_and_manifest_are_not_swallowed_by_spa_fallback(self) -> None:
        with mock.patch('web.views.resolve_service_worker_path', return_value=None):
            sw_response = self.client.get('/sw.js')
        manifest_response = self.client.get('/manifest.webmanifest')

        # SPA fallback renders the app shell with 200; these endpoints must not.
        self.assertEqual(sw_response.status_code, 404)
        self.assertEqual(manifest_response.status_code, 200)
        self.assertNotIn('text/html', manifest_response['Content-Type'])

    def test_spa_fallback_still_serves_unknown_routes(self) -> None:
        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
