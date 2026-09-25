"""Import task flow: one task per media item, orchestrator waits, then finishes.

    prepare_import_job     (after upload)          -> awaiting_confirmation
    run_import_job         (after user confirms)   -> processing
      ├─ resolve episode TMDB IDs to parent shows
      ├─ process_media_item ×N  (sync TMDB and TVMaze metadata for one item, apply its records)
      └─ waits for all of them, then calls finish_import():
           ├─ delete_missing_rows   (mirror mode only, explicit call site)
           ├─ reconcile             (canonical statuses; Up Next ready)
           └─ report + finish_apply

Every write is an idempotent upsert, so a retried item or a redelivered
orchestrator converges to the same final state.
"""

import logging

from celery import shared_task
from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Least

from ..choices import DataImportMode, DataTransferStatus
from ..import_engine import (
    apply_imported_lists,
    apply_item_records,
    build_final_report,
    delete_missing_rows,
    group_by_item,
    reconcile_user_media_status,
    touched_status_keys,
)
from ..import_records import ParsedImport
from ..import_resolution import candidate_show_ids, episode_parent_map, resolve_episode_records
from ..import_state_machine import fail, finish_apply, prepare_apply
from ..models import DataTransferJob, UserMediaStatus
from .import_commands import PrepareImportCommand
from .provider_registry import get_import_parser

logger = logging.getLogger(__name__)


class ImportJobCancelled(Exception):
    """Raised internally when an import is cancelled between task stages."""


def _ensure_processing(job: DataTransferJob) -> None:
    job.refresh_from_db()
    if job.status != DataTransferStatus.PROCESSING:
        raise ImportJobCancelled


def _load_parsed(job):
    content = job.input_file.read() if job.input_file else b''
    return get_import_parser(job.source)(content)


def _error_message(exc: Exception) -> str:
    message = getattr(exc, 'message', None) or str(exc)
    return message or exc.__class__.__name__


@shared_task(name='tracking.prepare_import_job', acks_late=True, reject_on_worker_lost=True)
def prepare_import_job(job_id: int) -> dict[str, str]:
    return PrepareImportCommand(job_id).execute()


@shared_task(name='tracking.sync_import_show_metadata', acks_late=True, reject_on_worker_lost=True)
def sync_import_show_metadata(job_id: int, tmdb_id: int) -> dict[str, str | bool]:
    """Synchronize one candidate show without applying tracking records."""
    job = DataTransferJob.objects.filter(id=job_id).first()
    if job is None:
        return {'status': 'missing'}
    try:
        _ensure_processing(job)
    except ImportJobCancelled:
        return {'status': 'cancelled'}

    from media.models import Season, TVShow
    from media.tmdb import tmdb

    if TVShow.objects.filter(tmdb_id=tmdb_id).exists() and Season.objects.filter(show__tmdb_id=tmdb_id).exists():
        return {'status': 'ok', 'cached': True}
    try:
        tmdb.sync_tv_show(tmdb_id, recompute_user_statuses=False, use_cache=True)
        return {'status': 'ok', 'cached': False}
    except Exception as exc:
        logger.warning('TMDB/TVMaze pre-resolution sync failed for tv %s: %s', tmdb_id, exc)
        return {'status': 'error', 'error': str(exc)}


def _set_import_stage(job: DataTransferJob, stage: str, counters: dict[str, int] | None = None):
    metadata = dict(job.metadata or {})
    pipeline = dict(metadata.get('pipeline') or {})
    pipeline['stage'] = stage
    if counters:
        merged = dict(pipeline.get('metadata_counters') or {})
        for key, value in counters.items():
            merged[key] = merged.get(key, 0) + value
        pipeline['metadata_counters'] = merged
    metadata['pipeline'] = pipeline
    job.metadata = metadata
    job.save(update_fields=['metadata', 'updated_at'])


def _resolve_episode_records(job: DataTransferJob, parsed: ParsedImport) -> tuple[ParsedImport, dict[str, int]]:
    if not parsed.unresolved_episodes:
        return parsed, {}

    _ensure_processing(job)
    _set_import_stage(job, 'resolving_episodes')
    episode_ids = {record.episode_tmdb_id for record in parsed.unresolved_episodes}
    parent_map = episode_parent_map(episode_ids)
    counters: dict[str, int] = {'metadata_fetches': 0, 'metadata_hits': 0, 'metadata_errors': 0}
    unresolved = [
        record
        for record in parsed.unresolved_episodes
        if len(parent_map.get(record.episode_tmdb_id, frozenset())) != 1
    ]
    candidates = set(candidate_show_ids(parsed)) if unresolved else set()

    candidate_ids = tuple(sorted(candidates))
    for start in range(0, len(candidate_ids), 2):
        _ensure_processing(job)
        batch = candidate_ids[start:start + 2]
        results = [sync_import_show_metadata.delay(job.id, tmdb_id) for tmdb_id in batch]
        for result in results:
            outcome = result.get(disable_sync_subtasks=False)
            if outcome.get('status') == 'cancelled':
                raise ImportJobCancelled
            if outcome.get('status') == 'error':
                counters['metadata_errors'] += 1
            elif outcome.get('cached'):
                counters['metadata_hits'] += 1
            else:
                counters['metadata_fetches'] += 1

    _ensure_processing(job)
    parent_map = episode_parent_map(episode_ids)
    resolved = resolve_episode_records(parsed, parent_map)
    return resolved, counters


@shared_task(name='tracking.run_import_job', acks_late=True, reject_on_worker_lost=True)
def run_import_job(job_id: int) -> dict[str, str]:
    from . import process_media_item

    job = DataTransferJob.objects.filter(id=job_id).first()
    if job is None:
        return {'status': 'missing'}
    if job.status != DataTransferStatus.PROCESSING:
        return {'status': job.status}

    try:
        prepare_apply(job)
        _ensure_processing(job)
        parsed = _load_parsed(job)
        parsed, resolution_counters = _resolve_episode_records(job, parsed)
        _ensure_processing(job)

        items = group_by_item(parsed)
        # Same number the confirmation recap showed: raw units from the file.
        total_items = int(parsed.report.get('total_items') or 0)

        # Snapshot status rows predating the import so NEW_ITEMS reconciliation
        # can tell "already tracked, leave alone" from "just created, finalize".
        touched = touched_status_keys(parsed)
        condition = Q()
        for media_type, tmdb_id in sorted(touched):
            condition |= Q(media_type=media_type, tmdb_id=tmdb_id)
        preexisting = (
            set(
                UserMediaStatus.objects.for_user(job.user)
                .filter(condition)
                .values_list('media_type', 'tmdb_id')
            )
            if touched
            else set()
        )
        metadata = dict(job.metadata or {})
        metadata['pipeline'] = {
            'stage': 'syncing',
            'applied': 0,
            'metadata_counters': resolution_counters,
            'preexisting_statuses': sorted([list(key) for key in preexisting]),
        }
        job.total_items = total_items
        job.processed_items = 0
        job.metadata = metadata
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'updated_at'])

        # Tracking rows become usable as items complete; TMDB and TVMaze calls
        # are cached, bundled per show, and parallel across workers.
        results = [process_media_item.delay(job_id, item) for item in items]
        # Orchestrator joins its own dispatched items; the explicit flag
        # opts out of Celery's "never .get() inside a task" guard.
        for result in results:
            result.get(disable_sync_subtasks=False)

        finish_import(job_id, parsed=parsed)

        job.refresh_from_db()
        return {'status': job.status}
    except ImportJobCancelled:
        job.refresh_from_db()
        return {'status': job.status}
    except Exception as exc:
        fail(job, _error_message(exc))
        return {'status': job.status}


@shared_task(name='tracking.process_media_item', acks_late=True, reject_on_worker_lost=True)
def process_media_item(job_id: int, item: dict, recompute_status: bool = False):
    """Sync TMDB catalog data and TVMaze TV enrichment, then apply tracking records."""
    from media.tmdb import tmdb

    job = DataTransferJob.objects.filter(id=job_id).first()
    if job is None:
        return
    if job.status != DataTransferStatus.PROCESSING:
        return

    try:
        sync_error = False
        if not _has_local_metadata(item['media_type'], item['tmdb_id']):
            try:
                if item['media_type'] == 'movie':
                    tmdb.sync_movie(item['tmdb_id'])
                else:
                    # recompute_status=False: reconciliation owns final statuses.
                    tmdb.sync_tv_show(item['tmdb_id'], recompute_user_statuses=recompute_status)
            except Exception as exc:
                # A bad id must never discard tracking data; count and continue.
                logger.warning('TMDB/TVMaze sync failed for %s %s: %s', item['media_type'], item['tmdb_id'], exc)
                sync_error = True

        job.refresh_from_db()
        if job.status != DataTransferStatus.PROCESSING:
            return

        applied = apply_item_records(
            job.user, item['media_type'], item['tmdb_id'], item['records'], job.import_mode
        )

        # Progress tracks the file's own records: items with big histories
        # move the bar proportionally; metadata-only items add 0.
        progress_delta = len(item['records'])
        if progress_delta:
            DataTransferJob.objects.filter(id=job_id).update(
                processed_items=Least('total_items', F('processed_items') + progress_delta),
            )
        _bump_pipeline(job_id, applied_delta=applied, counter_deltas={'metadata_errors': 1} if sync_error else {})
    except Exception:
        logger.exception('Failed processing %s %s for job %s', item['media_type'], item['tmdb_id'], job_id)
        raise


def _has_local_metadata(media_type: str, tmdb_id: int) -> bool:
    from media.models import Movie, Season, TVShow

    if media_type == 'movie':
        return Movie.objects.filter(tmdb_id=tmdb_id).exists()
    if media_type in ('tv', 'episode'):
        # A show without seasons was never fully synced; re-fetch so episodes
        # (Up Next) are available after the import.
        return (
            TVShow.objects.filter(tmdb_id=tmdb_id).exists()
            and Season.objects.filter(show__tmdb_id=tmdb_id).exists()
        )
    return False


def _bump_pipeline(job_id: int, applied_delta: int = 0, counter_deltas: dict | None = None):
    """Accumulate applied/counters under a row lock (idempotent-friendly)."""
    with transaction.atomic():
        job = DataTransferJob.objects.select_for_update().get(id=job_id)
        metadata = dict(job.metadata or {})
        pipeline = dict(metadata.get('pipeline') or {})
        if applied_delta:
            pipeline['applied'] = pipeline.get('applied', 0) + applied_delta
        if counter_deltas:
            counters = dict(pipeline.get('metadata_counters') or {})
            for name, delta in counter_deltas.items():
                counters[name] = counters.get(name, 0) + delta
            pipeline['metadata_counters'] = counters
        metadata['pipeline'] = pipeline
        job.metadata = metadata
        job.save(update_fields=['metadata', 'updated_at'])


def finish_import(job_id: int, parsed: ParsedImport | None = None):
    """Mirror deletions, reconcile canonical statuses, write report, finish."""
    job = DataTransferJob.objects.get(id=job_id)
    if job.status != DataTransferStatus.PROCESSING:
        return
    parsed = parsed or _load_parsed(job)
    pipeline = dict((job.metadata or {}).get('pipeline') or {})
    pipeline['stage'] = 'finalizing'

    import_mode = job.import_mode
    with transaction.atomic():
        deleted = {}
        if import_mode == DataImportMode.MIRROR_IMPORTED_SET:
            deleted = delete_missing_rows(job.user, parsed)
        applied_lists = apply_imported_lists(job.user, parsed, import_mode)

    preexisting = {tuple(key) for key in pipeline.get('preexisting_statuses') or []}
    reconcile_user_media_status(job.user, parsed, import_mode, preexisting)

    report = build_final_report(
        job,
        parsed,
        applied_count=pipeline.get('applied', 0),
        list_counts=applied_lists,
        metadata_state=pipeline.get('metadata_counters') or {},
    )
    report['deleted'] = deleted
    report['deleted_total'] = sum(deleted.values())
    metadata = dict(job.metadata or {})
    metadata['report'] = report
    metadata.update(report)
    metadata.pop('pipeline', None)
    job.metadata = metadata
    job.processed_items = job.total_items
    job.save(update_fields=['processed_items', 'metadata', 'updated_at'])
    finish_apply(job)
