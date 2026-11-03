import json
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings


class ViteAwareStaticFilesStorageTests:
    def test_collectstatic_hashes_django_assets_but_keeps_vite_output_names(self, tmp_path: Path) -> None:
        source = tmp_path / 'source'
        (source / 'web' / 'assets').mkdir(parents=True)
        (source / 'web' / 'assets' / 'main-abc123.js').write_text('export const a = 1')
        (source / 'branding').mkdir()
        (source / 'branding' / 'logo.svg').write_text('<svg/>')
        root = tmp_path / 'static_root'

        with override_settings(STATIC_ROOT=root, STATICFILES_DIRS=[source]):
            call_command('collectstatic', interactive=False, verbosity=0)
            paths = json.loads((root / 'staticfiles.json').read_text())['paths']

        assert paths['web/assets/main-abc123.js'] == 'web/assets/main-abc123.js'
        assert paths['branding/logo.svg'] != 'branding/logo.svg'
        assert (root / 'web' / 'assets' / 'main-abc123.js').read_text() == 'export const a = 1'
