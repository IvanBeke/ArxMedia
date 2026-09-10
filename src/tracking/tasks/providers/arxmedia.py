"""ArxMedia JSON import provider: pure parsing only (no DB/TMDB access)."""

import json

from django.utils import timezone

from ...choices import DataTransferFormat, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_metadata import _parse_watched_at, _safe_int
from ...import_records import (
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


def _report(records: tuple, invalid_count: int, unit_count: int, warnings: list[dict], list_count: int) -> dict:
    summary = {
        'watch_history': sum(1 for r in records if isinstance(r, WatchEntryRecord)),
        'watchlist': sum(1 for r in records if isinstance(r, StatusRecord) and r.status == TvShowStatus.PLAN_TO_WATCH),
        'ratings': sum(1 for r in records if isinstance(r, RatingRecord)),
        'lists': list_count,
    }
    return {
        'format': DataTransferFormat.JSON,
        'records_seen': unit_count,
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': unit_count,
        'warnings': warnings,
        'warnings_total': invalid_count,
        'warnings_truncated': invalid_count > len(warnings),
    }


def parse_arxmedia_json(content: bytes) -> ParsedImport:
    data = json.loads(content.decode('utf-8') or '{}')
    warnings: list[dict] = []
    invalid_count = 0
    if not isinstance(data, dict):
        add_import_warning(warnings, 'invalid_document', 'The JSON document must be an object.', {'kind': 'json_document'})
        data = {}

    def collection(name: str) -> list:
        nonlocal invalid_count
        value = data.get(name, [])
        if isinstance(value, list):
            return value
        if name in data:
            invalid_count += 1
            add_import_warning(warnings, 'invalid_collection', 'The collection must be an array.', {'kind': 'json_collection', 'collection': name})
        return []

    history = collection('watch_history')
    watchlist = collection('watchlist')
    ratings = collection('ratings')
    lists = collection('lists')

    records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []

    for index, item in enumerate(history, start=1):
        if not isinstance(item, dict):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_item', 'The watch history item must be an object.', {'kind': 'json_item', 'collection': WATCH_HISTORY_COLLECTION, 'index': index})
            continue
        media_type = item.get('media_type', WatchEntryMediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not tmdb_id:
            invalid_count += 1
            add_import_warning(warnings, 'missing_tmdb_id', 'The item does not contain a TMDB ID.', {'kind': 'json_item', 'collection': 'watch_history', 'index': index, 'field': 'tmdb_id'})
            continue
        records.append(
            WatchEntryRecord(
                media_type=media_type,
                tmdb_id=tmdb_id,
                watched_at=_parse_watched_at(item.get('watched_at')),
                season_number=_safe_int(item.get('season_number')),
                episode_number=_safe_int(item.get('episode_number')),
            )
        )

    for index, item in enumerate(watchlist, start=1):
        if not isinstance(item, dict):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_item', 'The watchlist item must be an object.', {'kind': 'json_item', 'collection': WATCHLIST_COLLECTION, 'index': index})
            continue
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not tmdb_id:
            invalid_count += 1
            add_import_warning(warnings, 'missing_tmdb_id', 'The item does not contain a TMDB ID.', {'kind': 'json_item', 'collection': 'watchlist', 'index': index, 'field': 'tmdb_id'})
            continue
        records.append(StatusRecord(
            media_type=media_type,
            tmdb_id=tmdb_id,
            status=TvShowStatus.PLAN_TO_WATCH,
            status_at=_parse_watched_at(item.get('plan_to_watch_at') or item.get('status_changed_at')),
        ))

    for index, item in enumerate(ratings, start=1):
        if not isinstance(item, dict):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_item', 'The rating item must be an object.', {'kind': 'json_item', 'collection': RATINGS_COLLECTION, 'index': index})
            continue
        score = _safe_int(item.get('score'))
        media_type = item.get('media_type', MediaType.MOVIE)
        tmdb_id = _safe_int(item.get('tmdb_id'))
        if not score or not tmdb_id:
            invalid_count += 1
            add_import_warning(warnings, 'invalid_rating', 'The rating item is missing a TMDB ID or valid score.', {'kind': 'json_item', 'collection': 'ratings', 'index': index, 'field': 'score' if not score else 'tmdb_id'})
            continue
        records.append(RatingRecord(media_type=media_type, tmdb_id=tmdb_id, score=score))

    parsed_lists: list[ListRecord] = []
    seen_list_names: set[str] = set()
    for index, list_data in enumerate(lists, start=1):
        if not isinstance(list_data, dict):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_list', 'The list must be an object.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index})
            continue
        name = list_data.get('name')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
            invalid_count += 1
            add_import_warning(
                warnings,
                'invalid_list',
                'The list name is missing or longer than 200 characters.',
                {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'name'},
            )
            continue
        name = name.strip()
        normalized_name = name.casefold()
        if normalized_name in seen_list_names:
            invalid_count += 1
            add_import_warning(warnings, 'duplicate_list', 'The import contains a duplicate list name.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'name'})
            continue
        seen_list_names.add(normalized_name)

        privacy = list_data.get('privacy', 'public')
        if privacy not in ('public', 'private'):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_list_privacy', 'The list privacy must be public or private; public was used.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'privacy'})
            privacy = 'public'

        raw_items = list_data.get('items', [])
        if not isinstance(raw_items, list):
            invalid_count += 1
            add_import_warning(warnings, 'invalid_list_items', 'The list items must be an array.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'field': 'items'})
            raw_items = []

        parsed_items: list[ListItemRecord] = []
        seen_items: set[tuple[str, int]] = set()
        for item_index, list_item in enumerate(raw_items, start=1):
            if not isinstance(list_item, dict):
                invalid_count += 1
                add_import_warning(warnings, 'invalid_list_item', 'The list item must be an object.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index})
                continue
            media_type = str(list_item.get('media_type') or '')
            tmdb_id = _safe_int(list_item.get('tmdb_id'))
            custom_order = _safe_int(list_item.get('custom_order'))
            if media_type not in (MediaType.MOVIE, MediaType.TV) or not tmdb_id or (custom_order is not None and custom_order < 0):
                invalid_count += 1
                add_import_warning(
                    warnings,
                    'invalid_list_item',
                    'The list item is missing a valid media type/TMDB ID or has an invalid order.',
                    {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index},
                )
                continue
            if (media_type, tmdb_id) in seen_items:
                invalid_count += 1
                add_import_warning(warnings, 'duplicate_list_item', 'The list contains a duplicate item.', {'kind': 'json_item', 'collection': LISTS_COLLECTION, 'index': index, 'item_index': item_index})
                continue
            seen_items.add((media_type, tmdb_id))
            parsed_items.append(ListItemRecord(
                media_type=media_type,
                tmdb_id=tmdb_id,
                custom_order=custom_order or 0,
                added_at=_parse_watched_at(list_item.get('added_at')) or timezone.now(),
            ))

        parsed_lists.append(ListRecord(
            name=name,
            description=list_data.get('description', '') if isinstance(list_data.get('description', ''), str) else '',
            privacy=privacy,
            items=tuple(parsed_items),
        ))

    collections: set[str] = set()
    if history:
        collections.add(WATCH_HISTORY_COLLECTION)
    if watchlist:
        collections.add(WATCHLIST_COLLECTION)
    if ratings:
        collections.add(RATINGS_COLLECTION)
    if parsed_lists or ('lists' in data and not lists):
        collections.add(LISTS_COLLECTION)

    unit_count = len(history) + len(watchlist) + len(ratings) + len(parsed_lists) + sum(
        len(record.items) for record in parsed_lists
    )
    report = _report(tuple(records), invalid_count, unit_count, warnings, len(parsed_lists))
    report['media_records_seen'] = len(history) + len(watchlist) + len(ratings)
    report['list_items_seen'] = sum(len(record.items) for record in parsed_lists)
    parsed = ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=report,
        prefetch_only_ids={
            MediaType.MOVIE: frozenset(item.tmdb_id for record in parsed_lists for item in record.items if item.media_type == MediaType.MOVIE),
            MediaType.TV: frozenset(item.tmdb_id for record in parsed_lists for item in record.items if item.media_type == MediaType.TV),
        },
        lists=tuple(parsed_lists),
    )
    return parsed


def analyze_arxmedia_json(content: bytes) -> dict:
    parsed = parse_arxmedia_json(content)
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
