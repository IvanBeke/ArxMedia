from .choices import DataTransferFormat, DataTransferSource

IMPORT_SOURCE_FORMATS: dict[str, str] = {
    DataTransferSource.ARXMEDIA: DataTransferFormat.JSON,
    DataTransferSource.TRAKT: DataTransferFormat.ZIP,
    DataTransferSource.YAMTRACK: DataTransferFormat.CSV,
}

IMPORT_SOURCE_CAPABILITIES: dict[str, dict[str, bool]] = {
    DataTransferSource.ARXMEDIA: {'requires_confirmation': True},
    DataTransferSource.TRAKT: {'requires_confirmation': True},
    DataTransferSource.YAMTRACK: {'requires_confirmation': True},
}


def expected_format_for_source(source: str) -> str | None:
    return IMPORT_SOURCE_FORMATS.get(source)


def supported_import_sources() -> tuple[str, ...]:
    return tuple(IMPORT_SOURCE_FORMATS.keys())


def source_requires_confirmation(source: str) -> bool:
    capability = IMPORT_SOURCE_CAPABILITIES.get(source, {})
    return bool(capability.get('requires_confirmation', False))
