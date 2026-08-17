from .choices import DataTransferStatus
from .import_errors import ImportDomainError, ImportErrorCode
from .models import DataTransferJob


def _assert_status(job: DataTransferJob, expected: str, code: str, message: str):
    if job.status != expected:
        raise ImportDomainError(code=code, message=message)


def start_prepare(job: DataTransferJob):
    _assert_status(
        job,
        DataTransferStatus.PENDING,
        ImportErrorCode.IMPORT_INVALID_STATE_TRANSITION,
        'Import job cannot start prepare from current status.',
    )
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])


def finish_prepare(job: DataTransferJob, report: dict):
    _assert_status(
        job,
        DataTransferStatus.PROCESSING,
        ImportErrorCode.IMPORT_INVALID_STATE_TRANSITION,
        'Import job cannot finish prepare from current status.',
    )
    job.total_items = report.get('total_items', 0)
    job.processed_items = 0
    job.metadata = report
    job.status = DataTransferStatus.AWAITING_CONFIRMATION
    job.error_message = ''
    job.save(update_fields=['total_items', 'processed_items', 'metadata', 'status', 'error_message', 'updated_at'])


def confirm(job: DataTransferJob, import_mode: str, overwrite_existing: bool):
    _assert_status(
        job,
        DataTransferStatus.AWAITING_CONFIRMATION,
        ImportErrorCode.IMPORT_NOT_READY,
        'Import job is not ready for confirmation.',
    )
    job.import_mode = import_mode
    job.overwrite_existing = overwrite_existing
    job.status = DataTransferStatus.PROCESSING
    job.processed_items = 0
    job.error_message = ''
    job.save(update_fields=['import_mode', 'overwrite_existing', 'status', 'processed_items', 'error_message', 'updated_at'])


def prepare_apply(job: DataTransferJob):
    _assert_status(
        job,
        DataTransferStatus.PROCESSING,
        ImportErrorCode.IMPORT_INVALID_STATE_TRANSITION,
        'Import job cannot apply from current status.',
    )
    job.processed_items = 0
    job.total_items = (job.metadata or {}).get('total_items', job.total_items)
    job.save(update_fields=['processed_items', 'total_items', 'updated_at'])


def finish_apply(job: DataTransferJob):
    _assert_status(
        job,
        DataTransferStatus.PROCESSING,
        ImportErrorCode.IMPORT_INVALID_STATE_TRANSITION,
        'Import job cannot be completed from current status.',
    )
    job.status = DataTransferStatus.DONE
    job.error_message = ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])


def fail(job: DataTransferJob, message: str):
    job.status = DataTransferStatus.FAILED
    job.error_message = message
    job.save(update_fields=['status', 'error_message', 'updated_at'])
