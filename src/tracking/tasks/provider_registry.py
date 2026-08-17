from collections.abc import Callable
from dataclasses import dataclass

from ..import_errors import ImportDomainError, ImportErrorCode
from .providers import (
    analyze_arxmedia_json,
    analyze_trakt_zip,
    analyze_yamtrack_csv,
    apply_arxmedia_json_import,
    apply_trakt_zip_import,
    apply_yamtrack_csv_import,
)
from .providers.base import ImportProvider


@dataclass
class FunctionImportProvider:
    prepare_fn: Callable[[bytes], dict]
    apply_fn: Callable

    def prepare(self, content: bytes) -> dict:
        return self.prepare_fn(content)

    def apply(self, job, content: bytes, import_mode: str) -> None:
        self.apply_fn(job, content, import_mode)


_PROVIDERS: dict[str, ImportProvider] = {
    'arxmedia': FunctionImportProvider(analyze_arxmedia_json, apply_arxmedia_json_import),
    'trakt': FunctionImportProvider(analyze_trakt_zip, apply_trakt_zip_import),
    'yamtrack': FunctionImportProvider(analyze_yamtrack_csv, apply_yamtrack_csv_import),
}


def get_import_provider(source: str) -> ImportProvider:
    provider = _PROVIDERS.get(source)
    if provider is None:
        raise ImportDomainError(
            code=ImportErrorCode.IMPORT_SOURCE_UNSUPPORTED,
            message=f'Unsupported import source: {source}',
        )
    return provider
