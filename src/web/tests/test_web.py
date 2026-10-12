"""Tests for PWA root-scope serving (manifest + service worker)."""

import tempfile
from pathlib import Path

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


class TestManifestView:
    def test_manifest_served_with_installability_fields(self, client: Client) -> None:
        response = client.get('/manifest.webmanifest')

        assert response.status_code == 200
        payload = response.json()
        assert payload['short_name'] == 'ArxMedia'
        assert payload['start_url'] == '/'
        assert payload['scope'] == '/'
        assert payload['display'] == 'standalone'
        assert payload['theme_color'] == '#9f42c6'
        sizes = [icon['sizes'] for icon in payload['icons']]
        assert '192x192' in sizes
        assert '512x512' in sizes
        assert any(icon.get('purpose') == 'maskable' for icon in payload['icons'])
        assert response['Cache-Control'] == 'public, max-age=86400'

    def test_manifest_has_json_content_type(self, client: Client) -> None:
        response = client.get('/manifest.webmanifest')

        assert response.status_code == 200
        assert 'application/json' in response['Content-Type']


class TestServiceWorkerView:
    def test_returns_404_when_ui_not_built(self, client: Client, mocker) -> None:
        mocker.patch('web.views.resolve_service_worker_path', return_value=None)
        response = client.get('/sw.js')

        assert response.status_code == 404

    def test_serves_built_worker_with_root_scope_headers(self, client: Client, mocker) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            worker = Path(tmpdir) / 'sw.js'
            worker.write_text('self.__WB_MANIFEST;')
            mocker.patch('web.views.resolve_service_worker_path', return_value=worker)
            response = client.get('/sw.js')

            assert response.status_code == 200
            assert response['Content-Type'] == 'application/javascript'
            assert response['Cache-Control'] == 'no-cache'
            assert response['Service-Worker-Allowed'] == '/'
            body = b''.join(response.streaming_content)  # type: ignore[attr-defined]
            assert body == b'self.__WB_MANIFEST;'

    def test_sw_and_manifest_are_not_swallowed_by_spa_fallback(self, client: Client, mocker) -> None:
        mocker.patch('web.views.resolve_service_worker_path', return_value=None)
        sw_response = client.get('/sw.js')
        manifest_response = client.get('/manifest.webmanifest')

        assert sw_response.status_code == 404
        assert manifest_response.status_code == 200
        assert 'text/html' not in manifest_response['Content-Type']

    def test_spa_fallback_still_serves_unknown_routes(self, client: Client, mocker) -> None:
        # No UI build exists in some environments (e.g. CI): stub the asset
        # tag and verify routing, not the build.
        loader_instance = mocker.patch(
            'django_vite.templatetags.django_vite.DjangoViteAssetLoader.instance'
        )
        loader_instance.return_value.generate_vite_asset.return_value = ''
        response = client.get('/dashboard')

        assert response.status_code == 200
        assert 'text/html' in response['Content-Type']
