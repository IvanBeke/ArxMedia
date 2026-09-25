"""Resolve source episode IDs to parent shows before applying tracking records."""

from collections import defaultdict

from media.models import Episode

from .choices import WatchEntryMediaType
from .import_records import (
    WATCH_HISTORY_COLLECTION,
    ParsedImport,
    WatchEntryRecord,
    add_import_warning,
)


def episode_parent_map(episode_ids: set[int]) -> dict[int, frozenset[int]]:
    """Return exact episode-ID to parent-show mappings from the local catalog."""
    if not episode_ids:
        return {}
    parents: dict[int, set[int]] = defaultdict(set)
    rows = Episode.objects.filter(tmdb_id__in=episode_ids).values_list(
        'tmdb_id', 'season__show__tmdb_id'
    )
    for episode_id, show_id in rows.iterator():
        if episode_id and show_id:
            parents[int(episode_id)].add(int(show_id))
    return {episode_id: frozenset(show_ids) for episode_id, show_ids in parents.items()}


def candidate_show_ids(parsed: ParsedImport) -> tuple[int, ...]:
    """Return source-provided show IDs to synchronize before ID resolution."""
    return tuple(sorted(parsed.show_ids_for_metadata))


def resolve_episode_records(parsed: ParsedImport, parent_map: dict[int, frozenset[int]]) -> ParsedImport:
    """Replace unresolved episode records with exact parent-show watch records."""
    if not parsed.unresolved_episodes:
        return parsed

    warnings = list(parsed.report.get('warnings') or [])
    records = list(parsed.records)
    invalid_count = parsed.invalid_count
    resolved_count = 0
    unresolved_count = 0

    for episode in parsed.unresolved_episodes:
        parent_ids = parent_map.get(episode.episode_tmdb_id, frozenset())
        location = {
            'kind': 'csv_row',
            'file': episode.origin,
            'row': episode.row_number,
            'column': 'tmdb_id',
        }
        if len(parent_ids) == 1:
            records.append(
                WatchEntryRecord(
                    media_type=WatchEntryMediaType.EPISODE,
                    tmdb_id=next(iter(parent_ids)),
                    watched_at=episode.watched_at,
                    season_number=episode.season_number,
                    episode_number=episode.episode_number,
                    origin=episode.origin,
                )
            )
            resolved_count += 1
            continue

        invalid_count += 1
        unresolved_count += 1
        if len(parent_ids) > 1:
            add_import_warning(
                warnings,
                'ambiguous_episode_parent',
                'The episode ID maps to more than one local parent show and was skipped.',
                location,
            )
        else:
            add_import_warning(
                warnings,
                'unresolved_episode',
                'The episode ID could not be matched to a local parent show and was skipped.',
                location,
            )

    collections = set(parsed.collections_present)
    if not any(isinstance(record, WatchEntryRecord) for record in records):
        collections.discard(WATCH_HISTORY_COLLECTION)

    report = dict(parsed.report)
    summary = dict(report.get('summary') or {})
    summary['watch_history'] = sum(
        1 for record in records if isinstance(record, WatchEntryRecord)
    )
    report['summary'] = summary
    report['invalid_count'] = invalid_count
    report['warnings'] = warnings
    report['warnings_total'] = invalid_count
    report['warnings_truncated'] = invalid_count > len(warnings)
    report['media_records_seen'] = len(records)
    report['resolved_episode_records'] = resolved_count
    report['unresolved_episode_records'] = unresolved_count

    return ParsedImport(
        records=tuple(records),
        collections_present=frozenset(collections),
        invalid_count=invalid_count,
        report=report,
        prefetch_only_ids=parsed.prefetch_only_ids,
        lists=parsed.lists,
    )
