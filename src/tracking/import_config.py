import io
import zipfile

from .choices import DataTransferFormat, DataTransferSource

MAX_IMPORT_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_IMPORT_ARCHIVE_ENTRIES = 1000
MAX_IMPORT_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024

IMPORT_SOURCE_FORMATS: dict[str, tuple[str, ...]] = {
    DataTransferSource.ARXMEDIA: (DataTransferFormat.ZIP,),
    DataTransferSource.TRAKT: (DataTransferFormat.ZIP,),
    DataTransferSource.WETRAKR: (DataTransferFormat.ZIP,),
    DataTransferSource.YAMTRACK: (DataTransferFormat.CSV,),
}

IMPORT_SOURCE_CAPABILITIES: dict[str, dict[str, bool]] = {
    DataTransferSource.ARXMEDIA: {'requires_confirmation': True},
    DataTransferSource.TRAKT: {'requires_confirmation': True},
    DataTransferSource.WETRAKR: {'requires_confirmation': True},
    DataTransferSource.YAMTRACK: {'requires_confirmation': True},
}


def expected_formats_for_source(source: str) -> tuple[str, ...] | None:
    return IMPORT_SOURCE_FORMATS.get(source)


def supported_import_sources() -> tuple[str, ...]:
    return tuple(IMPORT_SOURCE_FORMATS.keys())


def source_requires_confirmation(source: str) -> bool:
    capability = IMPORT_SOURCE_CAPABILITIES.get(source, {})
    return bool(capability.get('requires_confirmation', False))


def open_import_zip(content: bytes) -> zipfile.ZipFile:
    """Open an uploaded archive, rejecting zip bombs before any entry is decompressed."""
    archive = zipfile.ZipFile(io.BytesIO(content))
    entries = archive.infolist()
    if len(entries) > MAX_IMPORT_ARCHIVE_ENTRIES:
        archive.close()
        raise ValueError(f'Archive has too many files (limit {MAX_IMPORT_ARCHIVE_ENTRIES}).')
    if sum(entry.file_size for entry in entries) > MAX_IMPORT_ARCHIVE_UNCOMPRESSED_BYTES:
        archive.close()
        limit_mb = MAX_IMPORT_ARCHIVE_UNCOMPRESSED_BYTES // (1024 * 1024)
        raise ValueError(f'Archive is too large when extracted (limit {limit_mb} MB).')
    return archive
