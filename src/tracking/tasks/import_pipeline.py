from celery import shared_task

from .import_commands import ApplyImportCommand, PrepareImportCommand


@shared_task(name='tracking.prepare_arxmedia_json_import')
def prepare_arxmedia_json_import(job_id: int) -> dict[str, str]:
    return PrepareImportCommand(job_id).execute()


@shared_task(name='tracking.prepare_trakt_zip_import')
def prepare_trakt_zip_import(job_id: int) -> dict[str, str]:
    return PrepareImportCommand(job_id).execute()


@shared_task(name='tracking.prepare_yamtrack_csv_import')
def prepare_yamtrack_csv_import(job_id: int) -> dict[str, str]:
    return PrepareImportCommand(job_id).execute()


@shared_task(name='tracking.apply_arxmedia_json_import')
def apply_arxmedia_json_import(job_id: int) -> dict[str, str]:
    return ApplyImportCommand(job_id).execute()


@shared_task(name='tracking.apply_trakt_zip_import')
def apply_trakt_zip_import(job_id: int) -> dict[str, str]:
    return ApplyImportCommand(job_id).execute()


@shared_task(name='tracking.apply_yamtrack_csv_import')
def apply_yamtrack_csv_import(job_id: int) -> dict[str, str]:
    return ApplyImportCommand(job_id).execute()
