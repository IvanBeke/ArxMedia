"""ArxMedia backup import provider: pure parsing only (no DB/TMDB access)."""

import json

from django.utils import timezone

from ...choices import DataTransferFormat, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_config import open_import_zip
from ...import_metadata import _parse_watched_at, _safe_int
from ...import_records import (
    DROPPED_COLLECTION,
    LISTS_COLLECTION,
    RATINGS_COLLECTION,
    WATCH_HISTORY_COLLECTION,
    WATCHLIST_COLLECTION,
    ListItemRecord,
    ListRecord,
    ParsedImport,
    RatingRecord,
    StatusRecord,
    WatchEntryRecord,
    add_import_warning,
)

ARXMEDIA_ARCHIVE_FILES = {
    f'{collection}.json': collection
    for collection in (
        WATCH_HISTORY_COLLECTION,
        WATCHLIST_COLLECTION,
        RATINGS_COLLECTION,
        DROPPED_COLLECTION,
        LISTS_COLLECTION,
    )
}


def _report(
    records: tuple,
    invalid_count: int,
    unit_count: int,
    warnings: list[dict],
    list_count: int,
    data_format: str,
) -> dict:
    summary = {
        'watch_history': sum(1 for r in records if isinstance(r, WatchEntryRecord)),
        'watchlist': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.PLAN_TO_WATCH),
        'ratings': sum(1 for r in records if isinstance(r, RatingRecord)),
        'dropped': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.DROPPED),
        'lists': list_count,
    }
    return {
        'format': data_format,
        'records_seen': unit_count,
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': unit_count,
        'warnings': warnings,
        'warnings_total': invalid_count,
        'warnings_truncated': invalid_count > len(warnings),
    }


class _InvalidRowCounter:
    """Shared per-document invalid-row counter feeding the import warnings list."""

    def __init__(self, warnings: list[dict]):
        self.warnings = warnings
        self.count = 0

    def fail(self, code: str, message: str, location: dict) -> None:
        """Count one rejected row and attach its import warning."""
        self.count += 1
        add_import_warning(self.warnings, code, message, location)


def _read_collections(data: dict, errors: _InvalidRowCounter) -> tuple[list, list, list, list, list]:
    return (
        _read_collection(data, 'watch_history', errors),
        _read_collection(data, 'watchlist', errors),
        _read_collection(data, 'ratings', errors),
        _read_collection(data, 'dropped', errors),
        _read_collection(data, 'lists', errors),
    )


def _read_collection(data: dict, name: str, errors: _InvalidRowCounter) -> list:
    value = data.get(name, [])
    if isinstance(value, list):
        return value
    if name in data:
        errors.fail('invalid_collection', 'The collection must be an array.', {'kind': 'json_collection', 'collection': name})
    return []


def _collection_records(items, builder, errors: _InvalidRowCounter) -> list:
    records = []
    for index, item in enumerate(items, start=1):
        record = builder(item, index, errors)
        if record is not None:
            records.append(record)
    return records


def _history_record(item, index: int, errors: _InvalidRowCounter):
    if not isinstance(item, dict):
        errors.fail('invalid_item', 'The watch history item must be an object.', {'kind': 'json_item', 'collection': WATCH_HISTORY_COLLECTION, 'index': index})
        return None
    tmdb_id = _safe_int(item.get('tmdb_id'))
    if not tmdb_id:
        errors.fail('missing_tmdb_id', 'The item does not contain a TMDB ID.', {'kind': 'json_item', 'collection': 'watch_history', 'index': index, 'field': 'tmdb_id'})
        return None
    return WatchEntryRecord(
        media_type=item.get('media_type', WatchEntryMediaType.MOVIE),
        tmdb_id=tmdb_id,
        watched_at=_parse_watched_at(item.get('watched_at')),
        season_number=_safe_int(item.get('season_number')),
        episode_number=_safe_int(item.get('episode_number')),
    )


def _watchlist_record(item, index: int, errors: _InvalidRowCounter):
    if not isinstance(item, dict):
        errors.fail('invalid_item', 'The watchlist item must be an object.', {'kind': 'json_item', 'collection': WATCHLIST_COLLECTION, 'index': index})
        return None
    tmdb_id = _safe_int(item.get('tmdb_id'))
    if not tmdb_id:
        errors.fail('missing_tmdb_id', 'The item does not contain a TMDB ID.', {'kind': 'json_item', 'collection': 'watchlist', 'index': index, 'field': 'tmdb_id'})
        return None
    return StatusRecord(
        media_type=item.get('media_type', MediaType.MOVIE),
        tmdb_id=tmdb_id,
        status=TvShowStatus.PLAN_TO_WATCH,
        status_at=(
            _parse_watched_at(item.get('plan_to_watch_at'))
            or _parse_watched_at(item.get('status_changed_at'))
        ),
    )


def _dropped_record(item, index: int, errors: _InvalidRowCounter):
    if not isinstance(item, dict):
        errors.fail('invalid_item', 'The dropped item must be an object.', {'kind': 'json_item', 'collection': DROPPED_COLLECTION, 'index': index})
        return None
    tmdb_id = _safe_int(item.get('tmdb_id'))
    if not tmdb_id:
        errors.fail('missing_tmdb_id', 'The item does not contain a TMDB ID.', {'kind': 'json_item', 'collection': 'dropped', 'index': index, 'field': 'tmdb_id'})
        return None
    return StatusRecord(
        media_type=item.get('media_type', MediaType.MOVIE),
        tmdb_id=tmdb_id,
        status=TvShowStatus.DROPPED,
        status_at=(
            _parse_watched_at(item.get('dropped_at'))
            or _parse_watched_at(item.get('status_changed_at'))
        ),
    )


def _rating_missing_field(score, tmdb_id, rated_at) -> str:
    if not score:
        return 'score'
    return 'tmdb_id' if not tmdb_id else 'updated_at'


def _rating_record(item, index: int, errors: _InvalidRowCounter):
    if not isinstance(item, dict):
        errors.fail('invalid_item', 'The rating item must be an object.', {'kind': 'json_item', 'collection': RATINGS_COLLECTION, 'index': index})
        return None
    score = _safe_int(item.get('score'))
    tmdb_id = _safe_int(item.get('tmdb_id'))
    rated_at = _parse_watched_at(item.get('updated_at')) or _parse_watched_at(item.get('created_at'))
    if not score or not tmdb_id or rated_at is None:
        errors.fail('invalid_rating', 'The rating item is missing a TMDB ID, valid score, or valid rating date.', {'kind': 'json_item', 'collection': 'ratings', 'index': index, 'field': _rating_missing_field(score, tmdb_id, rated_at)})
        return None
    return RatingRecord(media_type=item.get('media_type', MediaType.MOVIE), tmdb_id=tmdb_id, score=score, rated_at=rated_at)


def _list_records(lists, errors: _InvalidRowCounter) -> list[ListRecord]:
    parsed_lists = []
    seen_list_names: set[str] = set()
    for index, list_data in enumerate(lists, start=1):
        record = _list_record(list_data, index, seen_list_names, errors)
        if record is not None:
            parsed_lists.append(record)
    return parsed_lists


def _list_record(list_data, index: int, seen_list_names, errors: _InvalidRowCounter):
    if not isinstance(list_data, dict):
        errors.fail('invalid_list', 'The list must be an object.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index})
        return None
    name = _valid_list_name(list_data, index, seen_list_names, errors)
    if name is None:
        return None
    raw_items = _list_raw_items(list_data, index, errors)
    return ListRecord(
        name=name,
        description=list_data.get('description', '') if isinstance(list_data.get('description', ''), str) else '',
        privacy=_list_privacy(list_data, index, errors),
        items=tuple(_list_items(raw_items, index, errors)),
    )


def _valid_list_name(list_data, index: int, seen_list_names, errors: _InvalidRowCounter):
    name = list_data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        errors.fail('invalid_list', 'The list name is missing or longer than 200 characters.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'name'})
        return None
    name = name.strip()
    normalized_name = name.casefold()
    if normalized_name in seen_list_names:
        errors.fail('duplicate_list', 'The import contains a duplicate list name.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'name'})
        return None
    seen_list_names.add(normalized_name)
    return name


def _list_privacy(list_data, index: int, errors: _InvalidRowCounter) -> str:
    privacy = list_data.get('privacy', 'public')
    if privacy in ('public', 'private'):
        return privacy
    errors.fail('invalid_list_privacy', 'The list privacy must be public or private; public was used.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'privacy'})
    return 'public'


def _list_raw_items(list_data, index: int, errors: _InvalidRowCounter) -> list:
    raw_items = list_data.get('items', [])
    if isinstance(raw_items, list):
        return raw_items
    errors.fail('invalid_list_items', 'The list items must be an array.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'items'})
    return []


def _list_item_invalid(media_type, tmdb_id, custom_order) -> bool:
    if media_type not in (MediaType.MOVIE, MediaType.TV) or not tmdb_id:
        return True
    return custom_order is not None and custom_order < 0


def _list_items(raw_items, index: int, errors: _InvalidRowCounter) -> list[ListItemRecord]:
    parsed_items = []
    seen_items: set[tuple[str, int]] = set()
    for item_index, list_item in enumerate(raw_items, start=1):
        record = _list_item_record(list_item, index, item_index, seen_items, errors)
        if record is not None:
            parsed_items.append(record)
    return parsed_items


def _list_item_record(list_item, index: int, item_index: int, seen_items, errors: _InvalidRowCounter):
    if not isinstance(list_item, dict):
        errors.fail('invalid_list_item', 'The list item must be an object.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index})
        return None
    media_type = str(list_item.get('media_type') or '')
    tmdb_id = _safe_int(list_item.get('tmdb_id'))
    custom_order = _safe_int(list_item.get('custom_order'))
    if _list_item_invalid(media_type, tmdb_id, custom_order):
        errors.fail('invalid_list_item', 'The list item is missing a valid media type/TMDB ID or has an invalid order.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index})
        return None
    if (media_type, tmdb_id) in seen_items:
        errors.fail('duplicate_list_item', 'The list contains a duplicate item.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index})
        return None
    seen_items.add((media_type, tmdb_id))
    return ListItemRecord(
        media_type=media_type,
        tmdb_id=tmdb_id,
        custom_order=custom_order or 0,
        added_at=_parse_watched_at(list_item.get('added_at')) or timezone.now(),
    )


def _present_collections(data, history, watchlist, ratings, dropped, parsed_lists, lists_value) -> frozenset:
    return frozenset(
        collection
        for collection, non_empty in (
            (WATCH_HISTORY_COLLECTION, history),
            (WATCHLIST_COLLECTION, watchlist),
            (RATINGS_COLLECTION, ratings),
            (DROPPED_COLLECTION, dropped),
            (LISTS_COLLECTION, parsed_lists or ('lists' in data and not lists_value)),
        )
        if non_empty
    )


def _list_item_ids(parsed_lists, media_type: str) -> frozenset[int]:
    return frozenset(
        item.tmdb_id
        for record in parsed_lists
        for item in record.items
        if item.media_type == media_type
    )


def _unit_count(history, watchlist, ratings, dropped, parsed_lists) -> int:
    return len(history) + len(watchlist) + len(ratings) + len(dropped) + len(parsed_lists) + sum(
        len(record.items) for record in parsed_lists
    )


def _parse_arxmedia_document(
    data,
    data_format: str,
    warnings: list[dict] | None = None,
    invalid_count: int = 0,
) -> ParsedImport:
    warnings = warnings if warnings is not None else []
    if not isinstance(data, dict):
        add_import_warning(warnings, 'invalid_document', 'The JSON document must be an object.', {'kind': 'json_document'})
        data = {}

    errors = _InvalidRowCounter(warnings)
    errors.count += invalid_count
    history, watchlist, ratings, dropped, lists = _read_collections(data, errors)

    records = []
    records += _collection_records(history, _history_record, errors)
    records += _collection_records(watchlist, _watchlist_record, errors)
    records += _collection_records(dropped, _dropped_record, errors)
    records += _collection_records(ratings, _rating_record, errors)
    parsed_lists = _list_records(lists, errors)

    report = _report(
        tuple(records), errors.count, _unit_count(history, watchlist, ratings, dropped, parsed_lists),
        warnings, len(parsed_lists), data_format,
    )
    report['media_records_seen'] = len(history) + len(watchlist) + len(ratings) + len(dropped)
    report['list_items_seen'] = sum(len(record.items) for record in parsed_lists)
    return ParsedImport(
        records=tuple(records),
        collections_present=_present_collections(data, history, watchlist, ratings, dropped, parsed_lists, lists),
        invalid_count=errors.count,
        report=report,
        prefetch_only_ids={
            MediaType.MOVIE: _list_item_ids(parsed_lists, MediaType.MOVIE),
            MediaType.TV: _list_item_ids(parsed_lists, MediaType.TV),
        },
        lists=tuple(parsed_lists),
    )


def parse_arxmedia_zip(content: bytes) -> ParsedImport:
    data = {}
    warnings: list[dict] = []
    invalid_count = 0
    files_report: list[dict] = []
    files_processed = 0
    files_failed = 0
    unsupported_files = 0
    seen_files: set[str] = set()

    with open_import_zip(content) as archive:
        for name in sorted(item.filename for item in archive.infolist() if not item.is_dir()):
            file_report = {'file': name, 'status': 'processed', 'records_seen': 0, 'error': ''}
            collection = ARXMEDIA_ARCHIVE_FILES.get(name)
            if collection is None:
                unsupported_files += 1
                file_report['status'] = 'unsupported'
                files_report.append(file_report)
                continue

            if name in seen_files:
                files_failed += 1
                invalid_count += 1
                file_report['status'] = 'failed'
                file_report['error'] = 'Duplicate archive entry.'
                add_import_warning(
                    warnings,
                    'duplicate_file',
                    'The archive contains the same collection file more than once.',
                    {'kind': 'zip_file', 'file': name},
                )
                files_report.append(file_report)
                continue
            files_processed += 1
            seen_files.add(name)

            try:
                document = json.loads(archive.read(name).decode('utf-8') or 'null')
            except Exception as exc:
                files_failed += 1
                invalid_count += 1
                file_report['status'] = 'failed'
                file_report['error'] = str(exc)
                add_import_warning(warnings, 'file_parse_error', str(exc), {'kind': 'zip_file', 'file': name})
                files_report.append(file_report)
                continue

            data[collection] = document
            file_report['records_seen'] = len(document) if isinstance(document, list) else 0
            files_report.append(file_report)

    parsed = _parse_arxmedia_document(data, DataTransferFormat.ZIP, warnings, invalid_count)
    parsed.report.update(
        {
            'files_processed': files_processed,
            'files_failed': files_failed,
            'unsupported_files': unsupported_files,
            'files': files_report,
        }
    )
    return parsed


def _analysis_report(parsed: ParsedImport) -> dict:
    report = dict(parsed.report)
    report.update(
        {
            'records_imported': 0,
            'records_skipped': parsed.report['records_seen'],
            'metadata_hits': 0,
            'metadata_fetches': 0,
            'metadata_errors': 0,
        }
    )
    return report


def analyze_arxmedia_zip(content: bytes) -> dict:
    return _analysis_report(parse_arxmedia_zip(content))
