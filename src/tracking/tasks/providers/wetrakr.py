"""WeTrackr ZIP import provider: pure parsing only (no DB/TMDB access)."""

import csv
import io
import zipfile
from datetime import datetime

from django.utils import timezone

from ...choices import DataTransferFormat, ListPrivacy, MediaType, TvShowStatus, WatchEntryMediaType
from ...import_config import open_import_zip
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


class _WeTrackrState:
    """Mutable state threaded through the per-file row handling."""

    def __init__(self) -> None:
        self.records: list[WatchEntryRecord | StatusRecord | RatingRecord] = []
        self.unresolved_episodes: list[UnresolvedEpisodeRecord] = []
        self.show_ids_for_metadata: set[int] = set()
        self.lists_by_name: dict[str, dict] = {}
        self.collections: set[str] = set()
        self.warnings: list[dict] = []
        self.files_report: list[dict] = []
        self.invalid_count = 0
        self.files_processed = 0
        self.files_failed = 0
        self.unsupported_files = 0
        self.unsupported_records = 0
        self.records_seen = 0
        self.skip_breakdown: dict[str, int] = {
            'skipped_missing_tmdb_id': 0,
            'skipped_unsupported_media_type': 0,
            'skipped_invalid_status': 0,
            'skipped_invalid_rating': 0,
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


def _reject(
    state: _WeTrackrState,
    code: str,
    message: str,
    file_name: str,
    row_number: int,
    column: str | None,
    counter: str | None = None,
) -> None:
    state.invalid_count += 1
    if counter:
        state.skip_breakdown[counter] += 1
    add_import_warning(
        state.warnings,
        code,
        message,
        {'kind': 'csv_row', 'file': file_name, 'row': row_number, 'column': column},
    )


def _wetrakr_root_files(archive: zipfile.ZipFile) -> set[str]:
    return {
        item.filename
        for item in archive.infolist()
        if not item.is_dir() and '/' not in item.filename and '\\' not in item.filename
    }


def _record_missing_file(state: _WeTrackrState, file_name: str, file_report: dict) -> None:
    state.files_failed += 1
    state.invalid_count += 1
    file_report['status'] = 'missing'
    add_import_warning(
        state.warnings,
        'missing_file',
        f'{file_name} is missing from the WeTrackr export.',
        {'kind': 'zip_file', 'file': file_name},
    )
    state.files_report.append(file_report)


def _record_failed_file(state: _WeTrackrState, file_name: str, file_report: dict, exc: Exception) -> None:
    state.files_failed += 1
    state.invalid_count += 1
    file_report['status'] = 'failed'
    file_report['error'] = str(exc)
    add_import_warning(state.warnings, 'file_parse_error', str(exc), {'kind': 'zip_file', 'file': file_name})
    state.files_report.append(file_report)


def _collect_show_ids(rows: list[dict], show_ids_for_metadata: set[int]) -> None:
    for row in rows:
        if (row.get('type') or '').strip().lower() == 'show':
            show_id = _positive_int(row.get('tmdb_id'))
            if show_id:
                show_ids_for_metadata.add(show_id)


def _unresolved_row_column(season_number, episode_number) -> str:
    return 'season_number' if season_number is None or season_number < 0 else 'episode_number'


def _tracklog_watched_episode(state: _WeTrackrState, file_name: str, row: dict, tmdb_id: int, index: int, event_at) -> None:
    season_number = _safe_int(row.get('season_number'))
    episode_number = _positive_int(row.get('episode_number'))
    if season_number is None or season_number < 0 or episode_number is None:
        _reject(
            state,
            'missing_episode_number',
            'The watched episode is missing a valid season or episode number.',
            file_name,
            index,
            _unresolved_row_column(season_number, episode_number),
        )
        return
    state.unresolved_episodes.append(
        UnresolvedEpisodeRecord(
            episode_tmdb_id=tmdb_id,
            season_number=season_number,
            episode_number=episode_number,
            watched_at=event_at,
            origin=file_name,
            row_number=index,
        )
    )


def _tracklog_watched(state: _WeTrackrState, file_name: str, row: dict, item_type: str, tmdb_id: int, index: int, event_at) -> None:
    if item_type == MediaType.MOVIE:
        state.records.append(
            WatchEntryRecord(
                media_type=WatchEntryMediaType.MOVIE,
                tmdb_id=tmdb_id,
                watched_at=event_at,
                origin=file_name,
            )
        )
        return
    if item_type == WatchEntryMediaType.EPISODE:
        _tracklog_watched_episode(state, file_name, row, tmdb_id, index, event_at)
        return
    state.records.append(
        StatusRecord(
            media_type=MediaType.TV,
            tmdb_id=tmdb_id,
            status=TvShowStatus.WATCHED,
            status_at=event_at,
            origin=file_name,
        )
    )


def _tracklog_status_row(state: _WeTrackrState, file_name: str, index: int, item_type: str, status: str, tmdb_id: int, event_at) -> None:
    mapped_status = WETRAKR_STATUS_MAP.get(status)
    mapped_media_type = _media_type(item_type)
    if not mapped_status or not mapped_media_type:
        state.unsupported_records += 1
        _reject(
            state,
            'unsupported_status',
            'The tracklog status cannot be mapped to an ArxMedia status.',
            file_name,
            index,
            'status',
            'skipped_invalid_status',
        )
        return
    state.records.append(
        StatusRecord(
            media_type=mapped_media_type,
            tmdb_id=tmdb_id,
            status=mapped_status,
            status_at=event_at,
            origin=file_name,
        )
    )
    if mapped_status == TvShowStatus.PLAN_TO_WATCH:
        state.collections.add(WATCHLIST_COLLECTION)


def _handle_tracklog_row(state: _WeTrackrState, file_name: str, row: dict, index: int) -> None:
    item_type = (row.get('type') or '').strip().lower()
    status = (row.get('status') or '').strip().lower()
    tmdb_id = _positive_int(row.get('tmdb_id'))
    if item_type not in {'movie', 'show', 'episode'}:
        state.unsupported_records += 1
        _reject(
            state,
            'unsupported_media_type',
            'The tracklog row uses an unsupported media type.',
            file_name,
            index,
            'type',
            'skipped_unsupported_media_type',
        )
        return
    if not tmdb_id:
        _reject(
            state,
            'missing_tmdb_id',
            'The tracklog row does not contain a valid TMDB ID.',
            file_name,
            index,
            'tmdb_id',
            'skipped_missing_tmdb_id',
        )
        return

    # tracked_at is the event date; updated_at is export/sync time
    # and must never stand in for a missing event date.
    event_at = _parse_watched_at(row.get('tracked_at'))
    if status == 'watched':
        _tracklog_watched(state, file_name, row, item_type, tmdb_id, index, event_at)
        return
    _tracklog_status_row(state, file_name, index, item_type, status, tmdb_id, event_at)


def _handle_tracklog_file(state: _WeTrackrState, file_name: str, rows: list[dict]) -> None:
    if rows:
        state.collections.add(WATCH_HISTORY_COLLECTION)
    for index, row in enumerate(rows, start=2):
        _handle_tracklog_row(state, file_name, row, index)


def _media_type_of(row: dict) -> str:
    return _media_type((row.get('type') or '').strip().lower())


def _rating_score_ok(score) -> bool:
    return score is not None and 1 <= score <= 10


def _invalid_rating_column(score) -> str:
    return 'rating' if not _rating_score_ok(score) else 'rated_at'


def _rating_valid(score, rated_at) -> bool:
    return _rating_score_ok(score) and rated_at is not None


def _handle_rating_row(state: _WeTrackrState, file_name: str, row: dict, index: int) -> None:
    media_type = _media_type_of(row)
    tmdb_id = _positive_int(row.get('tmdb_id'))
    score = _safe_int(row.get('rating'))
    rated_at = _parse_watched_at(row.get('rated_at'))
    if not media_type:
        state.unsupported_records += 1
        _reject(
            state,
            'unsupported_media_type',
            'The rating row uses an unsupported media type.',
            file_name,
            index,
            'type',
            'skipped_unsupported_media_type',
        )
        return
    if not tmdb_id:
        _reject(
            state,
            'missing_tmdb_id',
            'The rating row does not contain a valid TMDB ID.',
            file_name,
            index,
            'tmdb_id',
            'skipped_missing_tmdb_id',
        )
        return
    if not _rating_valid(score, rated_at):
        _reject(
            state,
            'invalid_rating',
            'The rating must be a whole number from 1 to 10 with a valid rated_at.',
            file_name,
            index,
            _invalid_rating_column(score),
            'skipped_invalid_rating',
        )
        return
    state.records.append(
        RatingRecord(
            media_type=media_type,
            tmdb_id=tmdb_id,
            score=score,
            rated_at=rated_at,
            origin=file_name,
        )
    )


def _handle_ratings_file(state: _WeTrackrState, file_name: str, rows: list[dict]) -> None:
    if rows:
        state.collections.add(RATINGS_COLLECTION)
    for index, row in enumerate(rows, start=2):
        _handle_rating_row(state, file_name, row, index)


def _upsert_list_item(
    state: _WeTrackrState,
    file_name: str,
    index: int,
    media_type: str,
    tmdb_id: int,
    *,
    list_name: str,
    description: str,
    rank: int,
    created_at: str | None,
) -> None:
    key = list_name.casefold()
    record = state.lists_by_name.setdefault(
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
        _reject(
            state,
            'duplicate_list_item',
            'The WeTrackr list contains a duplicate item.',
            file_name,
            index,
            'tmdb_id',
        )
        return
    record['seen'].add(item_key)
    record['items'].append(
        ListItemRecord(
            media_type=media_type,
            tmdb_id=tmdb_id,
            added_at=_timestamp(created_at or '') or timezone.now(),
            custom_order=rank - 1,
        )
    )


def _append_favorite_item(state: _WeTrackrState, file_name: str, row: dict, index: int, media_type: str, tmdb_id: int) -> None:
    _upsert_list_item(
        state,
        file_name,
        index,
        media_type,
        tmdb_id,
        list_name=WETRAKR_FAVORITES_LIST_NAME,
        description='Imported from WeTrackr.',
        rank=index - 1,
        created_at=row.get('created_at'),
    )


def _append_list_item(state: _WeTrackrState, file_name: str, row: dict, index: int, media_type: str, tmdb_id: int) -> None:
    raw_name = (row.get('list_name') or '').strip()
    if not raw_name or len(raw_name) > 200:
        _reject(
            state,
            'invalid_list_name',
            'The list name is missing or longer than 200 characters.',
            file_name,
            index,
            'list_name',
        )
        return
    rank = _positive_int(row.get('rank'))
    if rank is None:
        _reject(
            state,
            'invalid_list_rank',
            'The list rank is missing or invalid; file order was used.',
            file_name,
            index,
            'rank',
        )
        rank = index - 1
    _upsert_list_item(
        state,
        file_name,
        index,
        media_type,
        tmdb_id,
        list_name=raw_name,
        description=(row.get('list_description') or '').strip(),
        rank=rank,
        created_at=row.get('created_at'),
    )


def _handle_list_row(state: _WeTrackrState, file_name: str, row: dict, index: int) -> None:
    media_type = _media_type_of(row)
    tmdb_id = _positive_int(row.get('tmdb_id'))
    if not media_type:
        state.unsupported_records += 1
        _reject(
            state,
            'unsupported_media_type',
            'The list row uses an unsupported media type.',
            file_name,
            index,
            'type',
            'skipped_unsupported_media_type',
        )
        return
    if not tmdb_id:
        _reject(
            state,
            'missing_tmdb_id',
            'The list row does not contain a valid TMDB ID.',
            file_name,
            index,
            'tmdb_id',
            'skipped_missing_tmdb_id',
        )
        return

    if file_name == 'favorites.csv':
        _append_favorite_item(state, file_name, row, index, media_type, tmdb_id)
        return
    _append_list_item(state, file_name, row, index, media_type, tmdb_id)


def _handle_lists_file(state: _WeTrackrState, file_name: str, rows: list[dict]) -> None:
    state.collections.add(LISTS_COLLECTION)
    for index, row in enumerate(rows, start=2):
        _handle_list_row(state, file_name, row, index)


def _parse_rows_for_file(state: _WeTrackrState, file_name: str, rows: list[dict]) -> None:
    if file_name == 'tracklog.csv':
        _handle_tracklog_file(state, file_name, rows)
        return
    if file_name == 'ratings.csv':
        _handle_ratings_file(state, file_name, rows)
        return
    if file_name in {'favorites.csv', 'lists.csv'}:
        _handle_lists_file(state, file_name, rows)


def _process_wetrakr_file(archive: zipfile.ZipFile, file_name: str, root_files: set[str], state: _WeTrackrState) -> None:
    file_report: dict = {'file': file_name, 'status': 'processed', 'records_seen': 0, 'error': ''}
    if file_name not in root_files:
        _record_missing_file(state, file_name, file_report)
        return

    state.files_processed += 1
    try:
        rows = _read_csv(archive, file_name)
    except Exception as exc:
        _record_failed_file(state, file_name, file_report, exc)
        return

    file_report['records_seen'] = len(rows)
    state.records_seen += len(rows)
    _collect_show_ids(rows, state.show_ids_for_metadata)
    _parse_rows_for_file(state, file_name, rows)
    state.files_report.append(file_report)


def _mark_unsupported_files(state: _WeTrackrState, root_files: set[str]) -> None:
    for file_name in sorted(WETRAKR_IGNORED_FILES):
        if file_name in root_files:
            state.unsupported_files += 1
            state.files_report.append({'file': file_name, 'status': 'unsupported', 'records_seen': 0, 'error': ''})

    known_files = set(WETRAKR_SUPPORTED_FILES) | set(WETRAKR_IGNORED_FILES)
    for file_name in sorted(root_files - known_files):
        state.unsupported_files += 1
        state.files_report.append({'file': file_name, 'status': 'unsupported', 'records_seen': 0, 'error': ''})


def _wetrakr_summary(records: list, list_count: int, unresolved_count: int) -> dict:
    counts = {'watch_history': unresolved_count, 'watchlist': 0, 'ratings': 0, 'lists': list_count}
    for record in records:
        if isinstance(record, WatchEntryRecord):
            counts['watch_history'] += 1
        elif isinstance(record, StatusRecord) and record.status == TvShowStatus.PLAN_TO_WATCH:
            counts['watchlist'] += 1
        elif isinstance(record, RatingRecord):
            counts['ratings'] += 1
    return counts


def _list_items_by_media(parsed_lists: list, media_type: str) -> frozenset:
    return frozenset(
        item.tmdb_id for record in parsed_lists for item in record.items if item.media_type == media_type
    )


def _wetrakr_parsed_lists(state: _WeTrackrState) -> list:
    return [
        ListRecord(
            name=record['name'],
            description=record['description'],
            privacy=ListPrivacy.PRIVATE,
            items=tuple(record['items']),
        )
        for record in state.lists_by_name.values()
    ]


def _wetrakr_report(state: _WeTrackrState, parsed_lists: list) -> dict:
    records_seen = state.records_seen
    return {
        'format': DataTransferFormat.ZIP,
        'files_processed': state.files_processed,
        'files_failed': state.files_failed,
        'unsupported_files': state.unsupported_files,
        'unsupported_records': state.unsupported_records,
        'records_seen': records_seen,
        'invalid_count': state.invalid_count,
        'summary': _wetrakr_summary(
            state.records, len(parsed_lists), len(state.unresolved_episodes),
        ),
        'total_items': records_seen,
        'media_records_seen': len(state.records) + len(state.unresolved_episodes),
        'list_items_seen': sum(len(record.items) for record in parsed_lists),
        'unresolved_episode_records': len(state.unresolved_episodes),
        **state.skip_breakdown,
        'files': state.files_report,
        'warnings': state.warnings,
        'warnings_total': state.invalid_count,
        'warnings_truncated': state.invalid_count > len(state.warnings),
    }


def parse_wetrakr_zip(content: bytes) -> ParsedImport:
    state = _WeTrackrState()

    with open_import_zip(content) as archive:
        root_files = _wetrakr_root_files(archive)
        if not root_files.intersection(WETRAKR_SUPPORTED_FILES):
            raise ValueError('WeTrackr CSV files must be stored at the ZIP root.')

        for file_name in WETRAKR_SUPPORTED_FILES:
            _process_wetrakr_file(archive, file_name, root_files, state)
        _mark_unsupported_files(state, root_files)

    parsed_lists = _wetrakr_parsed_lists(state)
    return ParsedImport(
        records=tuple(state.records),
        collections_present=frozenset(state.collections),
        invalid_count=state.invalid_count,
        report=_wetrakr_report(state, parsed_lists),
        prefetch_only_ids={
            MediaType.MOVIE: _list_items_by_media(parsed_lists, MediaType.MOVIE),
            MediaType.TV: _list_items_by_media(parsed_lists, MediaType.TV),
        },
        lists=tuple(parsed_lists),
        unresolved_episodes=tuple(state.unresolved_episodes),
        show_ids_for_metadata=frozenset(state.show_ids_for_metadata),
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
