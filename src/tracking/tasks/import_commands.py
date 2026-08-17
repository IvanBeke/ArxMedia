from ..choices import DataImportMode, DataTransferJobType
from ..import_config import expected_format_for_source, source_requires_confirmation
from ..import_errors import ImportDomainError, ImportErrorCode
from ..import_state_machine import confirm as confirm_transition
from ..import_state_machine import fail, finish_apply, finish_prepare, prepare_apply, start_prepare
from ..models import DataTransferJob
from .provider_registry import get_import_provider


class PrepareImportCommand:
    def __init__(self, job_id: int):
        self.job_id = job_id

    def execute(self) -> dict[str, str]:
        job = DataTransferJob.objects.get(id=self.job_id)
        start_prepare(job)
        try:
            content = job.input_file.read() if job.input_file else b''
            provider = get_import_provider(job.source)
            report = provider.prepare(content)
            finish_prepare(job, report)
            return {'status': job.status}
        except Exception as exc:
            fail(job, str(exc))
            return {'status': job.status}


class ConfirmImportCommand:
    def __init__(self, job: DataTransferJob, import_mode: str):
        self.job = job
        self.import_mode = import_mode

    def execute(self):
        if self.job.job_type != DataTransferJobType.IMPORT:
            raise ImportDomainError(
                code=ImportErrorCode.IMPORT_CONFIRM_NOT_ALLOWED,
                message='Only import jobs can be confirmed.',
            )

        expected_format = expected_format_for_source(self.job.source)
        if expected_format is None:
            raise ImportDomainError(
                code=ImportErrorCode.IMPORT_SOURCE_UNSUPPORTED,
                message='Import source is not supported.',
            )
        if self.job.data_format != expected_format:
            raise ImportDomainError(
                code=ImportErrorCode.IMPORT_SOURCE_FORMAT_MISMATCH,
                message='Import source and format do not match.',
            )
        if not source_requires_confirmation(self.job.source):
            raise ImportDomainError(
                code=ImportErrorCode.IMPORT_CONFIRM_NOT_ALLOWED,
                message='Import source does not support confirmation.',
            )
        if self.import_mode not in DataImportMode.values:
            raise ImportDomainError(
                code=ImportErrorCode.IMPORT_MODE_INVALID,
                message='import_mode must be new_items, update_existing, or mirror_imported_set',
                field='import_mode',
            )

        overwrite_existing = self.import_mode in (DataImportMode.UPDATE_EXISTING, DataImportMode.MIRROR_IMPORTED_SET)
        confirm_transition(self.job, self.import_mode, overwrite_existing)


class ApplyImportCommand:
    def __init__(self, job_id: int):
        self.job_id = job_id

    def execute(self) -> dict[str, str]:
        job = DataTransferJob.objects.get(id=self.job_id)
        try:
            import_mode = job.import_mode or DataImportMode.NEW_ITEMS
            if import_mode not in DataImportMode.values:
                import_mode = DataImportMode.NEW_ITEMS

            prepare_apply(job)
            content = job.input_file.read() if job.input_file else b''
            provider = get_import_provider(job.source)
            provider.apply(job, content, import_mode)
            finish_apply(job)
            return {'status': job.status}
        except Exception as exc:
            fail(job, str(exc))
            return {'status': job.status}
