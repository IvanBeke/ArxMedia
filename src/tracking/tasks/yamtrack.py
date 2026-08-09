from celery import shared_task

from ..choices import DataImportMode, DataTransferStatus
from ..models import DataTransferJob
from .shared import YAMTRACK_IMPORT_SOURCE, _analyze_yamtrack_csv, _apply_yamtrack_csv


@shared_task(name="tracking.prepare_yamtrack_csv_import")
def prepare_yamtrack_csv_import(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        content = job.input_file.read() if job.input_file else b''
        report = _analyze_yamtrack_csv(content)
        job.total_items = report.get('total_items', 0)
        job.processed_items = 0
        metadata = dict(job.metadata or {})
        metadata.update(report)
        metadata['import_source'] = YAMTRACK_IMPORT_SOURCE
        job.metadata = metadata
        job.status = DataTransferStatus.AWAITING_CONFIRMATION
        job.error_message = ''
        job.save(update_fields=['total_items', 'processed_items', 'metadata', 'status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.AWAITING_CONFIRMATION}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}


@shared_task(name="tracking.apply_yamtrack_csv_import")
def apply_yamtrack_csv_import(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    try:
        import_mode = (job.metadata or {}).get('import_mode') or DataImportMode.NEW_ITEMS
        if import_mode not in DataImportMode.values:
            import_mode = DataImportMode.NEW_ITEMS
        content = job.input_file.read() if job.input_file else b''
        job.processed_items = 0
        job.total_items = (job.metadata or {}).get('total_items', job.total_items)
        job.save(update_fields=['processed_items', 'total_items', 'updated_at'])

        _apply_yamtrack_csv(job, content, import_mode)
        metadata = dict(job.metadata or {})
        metadata['import_mode'] = import_mode
        metadata['import_source'] = YAMTRACK_IMPORT_SOURCE
        job.metadata = metadata
        job.status = DataTransferStatus.DONE
        job.error_message = ''
        job.save(update_fields=['status', 'error_message', 'metadata', 'updated_at'])
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}
