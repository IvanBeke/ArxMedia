"""Canonical normalized import records.

Providers parse source files into these pure data structures; the import
engine is the single writer that turns them into database rows. Records carry
an ``origin`` label (file name or section) used only for reporting.
"""

import dataclasses
from datetime import datetime

from .choices import MediaType, WatchEntryMediaType

WATCH_HISTORY_COLLECTION = 'watch_history'
WATCHLIST_COLLECTION = 'watchlist'
RATINGS_COLLECTION = 'ratings'


def _dt_key(value: datetime | None) -> str:
    return value.isoformat() if value else ''


@dataclasses.dataclass(frozen=True)
class WatchEntryRecord:
    media_type: str  # WatchEntryMediaType: movie | episode
    tmdb_id: int
    watched_at: datetime | None = None
    season_number: int | None = None
    episode_number: int | None = None
    origin: str = ''

    @property
    def item_key(self) -> tuple[str, str, int]:
        return ('watch_entry', self.media_type, self.tmdb_id)

    def mirror_key(self) -> tuple:
        return (self.media_type, self.tmdb_id, self.season_number, self.episode_number)

    def sort_key(self) -> tuple:
        return (
            0,
            self.media_type,
            self.tmdb_id,
            self.season_number if self.season_number is not None else -1,
            self.episode_number if self.episode_number is not None else -1,
            _dt_key(self.watched_at),
        )


@dataclasses.dataclass(frozen=True)
class StatusRecord:
    media_type: str  # MediaType: movie | tv
    tmdb_id: int
    status: str  # TvShowStatus
    status_at: datetime | None = None
    progress: int | None = None  # TV watched-episodes hint from the source
    origin: str = ''

    def __post_init__(self):
        if self.media_type not in (MediaType.MOVIE, MediaType.TV):
            raise ValueError('StatusRecord.media_type must be movie or tv')

    @property
    def item_key(self) -> tuple[str, str, int]:
        return ('status', self.media_type, self.tmdb_id)

    def sort_key(self) -> tuple:
        return (1, self.media_type, self.tmdb_id, _dt_key(self.status_at), self.progress or 0)


@dataclasses.dataclass(frozen=True)
class RatingRecord:
    media_type: str  # MediaType: movie | tv
    tmdb_id: int
    score: int
    origin: str = ''

    @property
    def item_key(self) -> tuple[str, str, int]:
        return ('rating', self.media_type, self.tmdb_id)

    def sort_key(self) -> tuple:
        return (2, self.media_type, self.tmdb_id, self.score)


ImportRecord = WatchEntryRecord | StatusRecord | RatingRecord


@dataclasses.dataclass(frozen=True)
class ParsedImport:
    """Deterministic result of parsing an import file."""

    records: tuple[ImportRecord, ...]
    collections_present: frozenset[str]
    invalid_count: int
    report: dict  # Provider-specific static report (seen counts, files[], skipped_* breakdowns, total_items).
    prefetch_only_ids: dict[str, frozenset[int]] = dataclasses.field(default_factory=dict)  # ids needing metadata but producing no record

    def sorted_records(self) -> tuple[ImportRecord, ...]:
        return tuple(sorted(self.records, key=lambda record: record.sort_key()))

    def watch_entries(self) -> tuple[WatchEntryRecord, ...]:
        return tuple(record for record in self.records if isinstance(record, WatchEntryRecord))

    def statuses(self) -> tuple[StatusRecord, ...]:
        return tuple(record for record in self.records if isinstance(record, StatusRecord))

    def ratings(self) -> tuple[RatingRecord, ...]:
        return tuple(record for record in self.records if isinstance(record, RatingRecord))

    def unique_media_ids(self) -> dict[str, set[int]]:
        ids: dict[str, set[int]] = {
            MediaType.MOVIE: set(self.prefetch_only_ids.get(MediaType.MOVIE, ())),
            MediaType.TV: set(self.prefetch_only_ids.get(MediaType.TV, ())),
        }
        for record in self.records:
            media_type: str
            if isinstance(record, WatchEntryRecord):
                media_type = MediaType.TV if record.media_type == WatchEntryMediaType.EPISODE else MediaType.MOVIE
            else:
                media_type = record.media_type
            if media_type in ids:
                ids[media_type].add(record.tmdb_id)
        return ids

    def touched_item_keys(self) -> set[tuple[str, str, int]]:
        keys = set()
        for record in self.records:
            kind, media_type, tmdb_id = record.item_key
            media = MediaType.TV if (kind, media_type) == ('watch_entry', 'episode') else media_type
            keys.add((kind, media, tmdb_id))
        for media_type, ids in self.prefetch_only_ids.items():
            for tmdb_id in ids:
                keys.add(('prefetch', media_type, tmdb_id))
        return keys
