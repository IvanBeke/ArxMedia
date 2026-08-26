from collections.abc import Callable
from dataclasses import dataclass

from ..import_errors import ImportDomainError, ImportErrorCode
from .providers.arxmedia import analyze_arxmedia_json, parse_arxmedia_json
from .providers.trakt import analyze_trakt_zip, parse_trakt_zip
from .providers.yamtrack import analyze_yamtrack_csv, parse_yamtrack_csv


@dataclass(frozen=True)
class ImportProviderFunctions:
    analyze_fn: Callable[[bytes], dict]
    parse_fn: Callable[[bytes], object]

    def analyze(self, content: bytes) -> dict:
        return self.analyze_fn(content)

    def parse(self, content: bytes):
        return self.parse_fn(content)


_PROVIDERS: dict[str, ImportProviderFunctions] = {
    'arxmedia': ImportProviderFunctions(analyze_arxmedia_json, parse_arxmedia_json),
    'trakt': ImportProviderFunctions(analyze_trakt_zip, parse_trakt_zip),
    'yamtrack': ImportProviderFunctions(analyze_yamtrack_csv, parse_yamtrack_csv),
}


def get_import_provider(source: str) -> ImportProviderFunctions:
    provider = _PROVIDERS.get(source)
    if provider is None:
        raise ImportDomainError(
            code=ImportErrorCode.IMPORT_SOURCE_UNSUPPORTED,
            message=f'Unsupported import source: {source}',
        )
    return provider


def get_import_parser(source: str):
    return get_import_provider(source).parse_fn
