from typing import Any

from whitenoise.storage import CompressedManifestStaticFilesStorage

VITE_OUTPUT_PREFIX = 'web/'


class ViteAwareStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Keeps Vite's own content-hashed output under its emitted file names.

    Chunks import each other by relative URL, so serving the entry under a
    Django-hashed URL would load it a second time under the plain URL and run
    the app bootstrap twice.
    """

    def hashed_name(self, name: str, content: Any = None, filename: str | None = None) -> str:
        if name.startswith(VITE_OUTPUT_PREFIX):
            return name
        return super().hashed_name(name, content, filename)
