from dataclasses import dataclass

from rest_framework.exceptions import ValidationError


class ImportErrorCode:
    IMPORT_JOB_NOT_FOUND = 'IMPORT_JOB_NOT_FOUND'
    IMPORT_CONFIRM_NOT_ALLOWED = 'IMPORT_CONFIRM_NOT_ALLOWED'
    IMPORT_NOT_READY = 'IMPORT_NOT_READY'
    IMPORT_MODE_INVALID = 'IMPORT_MODE_INVALID'
    IMPORT_SOURCE_UNSUPPORTED = 'IMPORT_SOURCE_UNSUPPORTED'
    IMPORT_SOURCE_FORMAT_MISMATCH = 'IMPORT_SOURCE_FORMAT_MISMATCH'
    IMPORT_INVALID_STATE_TRANSITION = 'IMPORT_INVALID_STATE_TRANSITION'


@dataclass
class ImportDomainError(Exception):
    code: str
    message: str
    field: str = 'job'


def raise_import_validation_error(error: ImportDomainError):
    raise ValidationError({'error_code': error.code, error.field: error.message})
