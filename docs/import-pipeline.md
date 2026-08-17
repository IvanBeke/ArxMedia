# docs/import-pipeline.md - Tracking Import Architecture

This document describes the import architecture used by tracking data imports.

## Supported providers

- `arxmedia` (`json`)
- `trakt` (`zip`)
- `yamtrack` (`csv`)

Source and format compatibility is defined in `src/tracking/import_config.py` via
`IMPORT_SOURCE_FORMATS`.

## Unified flow

All providers follow the same lifecycle:

1. Upload import file (`POST /api/tracking/data/import/`)
2. Prepare task runs provider analysis
3. Job transitions to `awaiting_confirmation`
4. User selects `import_mode`
5. Confirm endpoint starts apply task
6. Apply task finishes job as `done` or `failed`

## Pattern mapping

- **State Machine**: `src/tracking/import_state_machine.py`
  - Centralized status transitions for prepare/confirm/apply/fail.
- **Strategy**: `src/tracking/tasks/provider_registry.py` + `src/tracking/tasks/providers/`
  - Provider-specific prepare/apply behavior is encapsulated per source.
- **Command**: `src/tracking/tasks/import_commands.py`
  - Orchestrates workflow units (`PrepareImportCommand`, `ConfirmImportCommand`, `ApplyImportCommand`).

## Canonical job fields

- `source`: provider identity (`arxmedia`, `trakt`, `yamtrack`)
- `import_mode`: selected import behavior (`new_items`, `update_existing`, `mirror_imported_set`)
- `status`: lifecycle state
- `metadata`: report payload (summary, counters, provider-specific diagnostics)

Control state is not stored in metadata.

## Error contract

Import errors use machine-readable error codes from `src/tracking/import_errors.py`.

Current codes:

- `IMPORT_JOB_NOT_FOUND`
- `IMPORT_CONFIRM_NOT_ALLOWED`
- `IMPORT_NOT_READY`
- `IMPORT_MODE_INVALID`
- `IMPORT_SOURCE_UNSUPPORTED`
- `IMPORT_SOURCE_FORMAT_MISMATCH`
- `IMPORT_INVALID_STATE_TRANSITION`

API responses include `error_code` and a field-specific message.

## Task entrypoints

Celery task names retained by wrappers in `src/tracking/tasks/import_pipeline.py`:

- `tracking.prepare_arxmedia_json_import`
- `tracking.prepare_trakt_zip_import`
- `tracking.prepare_yamtrack_csv_import`
- `tracking.apply_arxmedia_json_import`
- `tracking.apply_trakt_zip_import`
- `tracking.apply_yamtrack_csv_import`

## Notes for future providers

To add a new provider:

1. Add source and format mapping in `import_config.py`
2. Implement provider functions under `src/tracking/tasks/providers/`
3. Register provider in `provider_registry.py`
4. Wire task wrappers if new queue names are needed
5. Add tests for prepare, confirm, apply, and error handling
