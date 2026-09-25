"""WeTrackr ZIP import provider: pure parsing only (no DB/TMDB access)."""

import csv
import io
import zipfile
from datetime import datetime

from django.utils import timezone

from ...choices import DataTransferFormat, ListPrivacy, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_metadata import UNKNOWN_IMPORTED_DATE, _parse_watched_at, _safe_int
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
    UnresolvedEpisodeRecord,
    WatchEntryRecord,
    add_import_warning,
)

WETRAKR_FAVORITES_LIST_NAME = 'Favorites (WeTrackr)'
WETRAKR_SUPPORTED_FILES = ('tracklog.csv', 'ratings.csv', 'favorites.csv', 'lists.csv')
WETRAKR_IGNORED_FILES = ('notes.csv', 'profile.csv')
WETRAKR_REQUIRED_HEADERS = {
    'tracklog.csv': {'type', 'tmdb_id', 'season_number', 'episode_number', 'status', 'tracked_at', 'updated_at'},
    'ratings.csv': {'type', 'tmdb_id', 'rating', 'rated_at'},
    'favorites.csv': {'type', 'tmdb_id', 'created_at'},
    'lists.csv': {'list_name', 'list_description', 'type', 'tmdb_id', 'rank', 'created_at'},
}
WETRAKR_STATUS_MAP = {
    'watching': TvShowStatus.WATCHING,
    'waiting': TvShowStatus.WATCHING,
    'paused': TvShowStatus.WATCHING,
    'plantowatch': TvShowStatus.PLAN_TO_WATCH,
    'planning': TvShowStatus.PLAN_TO_WATCH,
    'discarded': TvShowStatus.DROPPED,
    'dropped': TvShowStatus.DROPPED,
}


def _positive_int(value) -> int | None:
    parsed = _safe_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _media_type(value: str) -> str:
    return {
        'movie': MediaType.MOVIE,
        'show': MediaType.TV,
    }.get(value, '')


def _read_csv(archive: zipfile.ZipFile, file_name: str) -> list[dict]:
    text = archive.read(file_name).decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    headers = set(reader.fieldnames or ())
    missing = sorted(WETRAKR_REQUIRED_HEADERS[file_name] - headers)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return list(reader)


def _timestamp(*values: str) -> datetime | None:
    for value in values:
        parsed = _parse_watched_at(value)
        if parsed is not None:
            return parsed
    return None


def parse_wetrakr_zip(content: bytes) -> ParsedImport:
    records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
    unresolved_episodes: list[UnresolvedEpisodeRecord] = []
    show_ids_for_metadata: set[int] = set()
    lists_by_name: dict[str, dict] = {}
    collections: set[str] = set()
    warnings: list[dict] = []
    files_report: list[dict] = []
    invalid_count = 0
    files_processed = 0
    files_failed = 0
    unsupported_files = 0
    unsupported_records = 0
    records_seen = 0
    skip_breakdown = {
        'skipped_missing_tmdb_id': 0,
        'skipped_unsupported_media_type': 0,
        'skipped_invalid_status': 0,
        'skipped_invalid_rating': 0,
    }

    def reject(
        code: str,
        message: str,
        file_name: str,
        row_number: int,
        column: str,
        counter: str | None = None,
    ) -> None:
        nonlocal invalid_count
        invalid_count += 1
        if counter:
            skip_breakdown[counter] += 1
        add_import_warning(
            warnings,
            code,
            message,
            {'kind': 'csv_row', 'file': file_name, 'row': row_number, 'column': column},
        )

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root_files = {
            item.filename
            for item in archive.infolist()
            if not item.is_dir() and '/' not in item.filename and '\\' not in item.filename
        }
        if not root_files.intersection(WETRAKR_SUPPORTED_FILES):
            raise ValueError('WeTrackr CSV files must be stored at the ZIP root.')

        for file_name in WETRAKR_SUPPORTED_FILES:
            file_report = {'file': file_name, 'status': 'processed', 'records_seen': 0, 'error': ''}
            if file_name not in root_files:
                files_failed += 1
                invalid_count += 1
                file_report['status'] = 'missing'
                add_import_warning(
                    warnings,
                    'missing_file',
                    f'{file_name} is missing from the WeTrackr export.',
                    {'kind': 'zip_file', 'file': file_name},
                )
                files_report.append(file_report)
                continue

            files_processed += 1
            try:
                rows = _read_csv(archive, file_name)
            except Exception as exc:
                files_failed += 1
                invalid_count += 1
                file_report['status'] = 'failed'
                file_report['error'] = str(exc)
                add_import_warning(warnings, 'file_parse_error', str(exc), {'kind': 'zip_file', 'file': file_name})
                files_report.append(file_report)
                continue

            file_report['records_seen'] = len(rows)
            records_seen += len(rows)
            for row in rows:
                if (row.get('type') or '').strip().lower() == 'show':
                    show_id = _positive_int(row.get('tmdb_id'))
                    if show_id:
                        show_ids_for_metadata.add(show_id)

            if file_name == 'tracklog.csv':
                if rows:
                    collections.add(WATCH_HISTORY_COLLECTION)
                for index, row in enumerate(rows, start=2):
                    item_type = (row.get('type') or '').strip().lower()
                    status = (row.get('status') or '').strip().lower()
                    tmdb_id = _positive_int(row.get('tmdb_id'))
                    if item_type not in {'movie', 'show', 'episode'}:
                        unsupported_records += 1
                        reject(
                            'unsupported_media_type',
                            'The tracklog row uses an unsupported media type.',
                            file_name,
                            index,
                            'type',
                            'skipped_unsupported_media_type',
                        )
                        continue
                    if not tmdb_id:
                        reject(
                            'missing_tmdb_id',
                            'The tracklog row does not contain a valid TMDB ID.',
                            file_name,
                            index,
                            'tmdb_id',
                            'skipped_missing_tmdb_id',
                        )
                        continue

                    # tracked_at is the event date; updated_at is export/sync time
                    # and must never stand in for a missing event date.
                    event_at = _parse_watched_at(row.get('tracked_at')) or UNKNOWN_IMPORTED_DATE
                    if status == 'watched':
                        if item_type == MediaType.MOVIE:
                            records.append(
                                WatchEntryRecord(
                                    media_type=WatchEntryMediaType.MOVIE,
                                    tmdb_id=tmdb_id,
                                    watched_at=event_at,
                                    origin=file_name,
                                )
                            )
                        elif item_type == WatchEntryMediaType.EPISODE:
                            season_number = _safe_int(row.get('season_number'))
                            episode_number = _positive_int(row.get('episode_number'))
                            if season_number is None or season_number < 0 or episode_number is None:
                                reject(
                                    'missing_episode_number',
                                    'The watched episode is missing a valid season or episode number.',
                                    file_name,
                                    index,
                                    'season_number' if season_number is None or season_number < 0 else 'episode_number',
                                )
                                continue
                            unresolved_episodes.append(
                                UnresolvedEpisodeRecord(
                                    episode_tmdb_id=tmdb_id,
                                    season_number=season_number,
                                    episode_number=episode_number,
                                    watched_at=event_at,
                                    origin=file_name,
                                    row_number=index,
                                )
                            )
                        else:
                            records.append(
                                StatusRecord(
                                    media_type=MediaType.TV,
                                    tmdb_id=tmdb_id,
                                    status=TvShowStatus.WATCHED,
                                    status_at=event_at,
                                    origin=file_name,
                                )
                            )
                        continue

                    mapped_status = WETRAKR_STATUS_MAP.get(status)
                    mapped_media_type = _media_type(item_type)
                    if not mapped_status or not mapped_media_type:
                        unsupported_records += 1
                        reject(
                            'unsupported_status',
                            'The tracklog status cannot be mapped to an ArxMedia status.',
                            file_name,
                            index,
                            'status',
                            'skipped_invalid_status',
                        )
                        continue
                    records.append(
                        StatusRecord(
                            media_type=mapped_media_type,
                            tmdb_id=tmdb_id,
                            status=mapped_status,
                            status_at=event_at,
                            origin=file_name,
                        )
                    )
                    if mapped_status == TvShowStatus.PLAN_TO_WATCH:
                        collections.add(WATCHLIST_COLLECTION)

            elif file_name == 'ratings.csv':
                if rows:
                    collections.add(RATINGS_COLLECTION)
                for index, row in enumerate(rows, start=2):
                    media_type = _media_type((row.get('type') or '').strip().lower())
                    tmdb_id = _positive_int(row.get('tmdb_id'))
                    score = _safe_int(row.get('rating'))
                    rated_at = _parse_watched_at(row.get('rated_at'))
                    if not media_type:
                        unsupported_records += 1
                        reject(
                            'unsupported_media_type',
                            'The rating row uses an unsupported media type.',
                            file_name,
                            index,
                            'type',
                            'skipped_unsupported_media_type',
                        )
                        continue
                    if not tmdb_id:
                        reject(
                            'missing_tmdb_id',
                            'The rating row does not contain a valid TMDB ID.',
                            file_name,
                            index,
                            'tmdb_id',
                            'skipped_missing_tmdb_id',
                        )
                        continue
                    if score is None or not 1 <= score <= 10 or rated_at is None:
                        reject(
                            'invalid_rating',
                            'The rating must be a whole number from 1 to 10 with a valid rated_at.',
                            file_name,
                            index,
                            'rating' if score is None or not 1 <= score <= 10 else 'rated_at',
                            'skipped_invalid_rating',
                        )
                        continue
                    records.append(
                        RatingRecord(
                            media_type=media_type,
                            tmdb_id=tmdb_id,
                            score=score,
                            rated_at=rated_at,
                            origin=file_name,
                        )
                    )

            elif file_name in {'favorites.csv', 'lists.csv'}:
                collections.add(LISTS_COLLECTION)
                for index, row in enumerate(rows, start=2):
                    media_type = _media_type((row.get('type') or '').strip().lower())
                    tmdb_id = _positive_int(row.get('tmdb_id'))
                    if not media_type:
                        unsupported_records += 1
                        reject(
                            'unsupported_media_type',
                            'The list row uses an unsupported media type.',
                            file_name,
                            index,
                            'type',
                            'skipped_unsupported_media_type',
                        )
                        continue
                    if not tmdb_id:
                        reject(
                            'missing_tmdb_id',
                            'The list row does not contain a valid TMDB ID.',
                            file_name,
                            index,
                            'tmdb_id',
                            'skipped_missing_tmdb_id',
                        )
                        continue

                    rank: int | None
                    if file_name == 'favorites.csv':
                        list_name = WETRAKR_FAVORITES_LIST_NAME
                        description = 'Imported from WeTrackr.'
                        rank = index - 1
                        created_at = row.get('created_at')
                    else:
                        raw_name = (row.get('list_name') or '').strip()
                        if not raw_name or len(raw_name) > 200:
                            reject(
                                'invalid_list_name',
                                'The list name is missing or longer than 200 characters.',
                                file_name,
                                index,
                                'list_name',
                            )
                            continue
                        list_name = raw_name
                        description = (row.get('list_description') or '').strip()
                        rank = _positive_int(row.get('rank'))
                        if rank is None:
                            reject(
                                'invalid_list_rank',
                                'The list rank is missing or invalid; file order was used.',
                                file_name,
                                index,
                                'rank',
                            )
                            rank = index - 1
                        created_at = row.get('created_at')

                    key = list_name.casefold()
                    record = lists_by_name.setdefault(
                        key,
                        {
                            'name': list_name,
                            'description': description,
                            'items': [],
                            'seen': set(),
                        },
                    )
                    if description and not record['description']:
                        record['description'] = description
                    item_key = (media_type, tmdb_id)
                    if item_key in record['seen']:
                        reject(
                            'duplicate_list_item',
                            'The WeTrackr list contains a duplicate item.',
                            file_name,
                            index,
                            'tmdb_id',
                        )
                        continue
                    record['seen'].add(item_key)
                    record['items'].append(
                        ListItemRecord(
                            media_type=media_type,
                            tmdb_id=tmdb_id,
                            added_at=_timestamp(created_at or '') or timezone.now(),
                            custom_order=rank - 1,
                        )
                    )

            files_report.append(file_report)

        for file_name in sorted(WETRAKR_IGNORED_FILES):
            if file_name in root_files:
                unsupported_files += 1
                files_report.append({'file': file_name, 'status': 'unsupported', 'records_seen': 0, 'error': ''})

        known_files = set(WETRAKR_SUPPORTED_FILES) | set(WETRAKR_IGNORED_FILES)
        for file_name in sorted(root_files - known_files):
            unsupported_files += 1
            files_report.append({'file': file_name, 'status': 'unsupported', 'records_seen': 0, 'error': ''})

    parsed_lists = [
        ListRecord(
            name=record['name'],
            description=record['description'],
            privacy=ListPrivacy.PRIVATE,
            items=tuple(record['items']),
        )
        for record in lists_by_name.values()
    ]
    summary = {
        'watch_history': sum(1 for record in records if isinstance(record, WatchEntryRecord)) + len(unresolved_episodes),
        'watchlist': sum(
            1
            for record in records
            if isinstance(record, StatusRecord) and record.status == TvShowStatus.PLAN_TO_WATCH
        ),
        'ratings': sum(1 for record in records if isinstance(record, RatingRecord)),
        'lists': len(parsed_lists),
    }
    report = {
        'format': DataTransferFormat.ZIP,
        'files_processed': files_processed,
        'files_failed': files_failed,
        'unsupported_files': unsupported_files,
        'unsupported_records': unsupported_records,
        'records_seen': records_seen,
        'invalid_count': invalid_count,
        'summary': summary,
        'total_items': records_seen,
        'media_records_seen': len(records) + len(unresolved_episodes),
        'list_items_seen': sum(len(record.items) for record in parsed_lists),
        'unresolved_episode_records': len(unresolved_episodes),
        **skip_breakdown,
        'files': files_report,
        'warnings': warnings,
        'warnings_total': invalid_count,
        'warnings_truncated': invalid_count > len(warnings),
    }
    return ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=report,
        prefetch_only_ids={
            MediaType.MOVIE: frozenset(
                item.tmdb_id for record in parsed_lists for item in record.items if item.media_type == MediaType.MOVIE
            ),
            MediaType.TV: frozenset(
                item.tmdb_id for record in parsed_lists for item in record.items if item.media_type == MediaType.TV
            ),
        },
        lists=tuple(parsed_lists),
        unresolved_episodes=tuple(unresolved_episodes),
        show_ids_for_metadata=frozenset(show_ids_for_metadata),
    )


def analyze_wetrakr_zip(content: bytes) -> dict:
    parsed = parse_wetrakr_zip(content)
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
