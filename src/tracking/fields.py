import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models

logger = logging.getLogger(__name__)


class EncryptedText(models.TextField):
    description = 'Text stored encrypted with Fernet'

    @staticmethod
    def _fernet() -> Fernet:
        key = getattr(settings, 'FERNET_KEY', '')
        if not key:
            raise ImproperlyConfigured('FERNET_KEY must be configured to use EncryptedText.')
        if isinstance(key, str):
            key = key.encode('utf-8')
        try:
            return Fernet(key)
        except Exception as exc:
            raise ImproperlyConfigured('FERNET_KEY is invalid for Fernet.') from exc

    def _decrypt_value(self, value: str):
        try:
            raw = value.encode('utf-8')
        except Exception:
            return False, value

        try:
            return True, self._fernet().decrypt(raw).decode('utf-8')
        except (InvalidToken, ValueError, TypeError):
            return False, value
        except Exception:
            return None, value

    def get_prep_value(self, value):
        if value is None:
            return value
        if not isinstance(value, str):
            value = str(value)
        if value in (None, ''):
            return value
        encrypted = self._fernet().encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')

    def from_db_value(self, value, expression, connection):
        if value in (None, ''):
            return value
        if not isinstance(value, str):
            return value

        ok, decrypted = self._decrypt_value(value)
        if ok is True:
            return decrypted

        logger.error('EncryptedText failed to decrypt DB value for field %s', self.name)
        if not settings.DEBUG:
            raise ValidationError('Invalid encrypted value in database.')
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in (None, ''):
            return value
        if not isinstance(value, str):
            return value

        ok, decrypted = self._decrypt_value(value)
        if ok is True:
            return decrypted
        return value
