"""Resolve the `watched_at` value sent by clients into a timestamp.

Clients send one of:
- "now" (or nothing): the current time
- "unknown": the shared unknown-date marker (1970-01-01 UTC)
- "release_date": when the item was released; falls back to now when no date is stored
- an ISO 8601 timestamp: that exact moment
"""

from datetime import date, datetime

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .import_metadata import UNKNOWN_IMPORTED_DATE

WATCHED_AT_NOW = 'now'
WATCHED_AT_UNKNOWN = 'unknown'
WATCHED_AT_RELEASE_DATE = 'release_date'


def wants_release_date(value) -> bool:
    return value == WATCHED_AT_RELEASE_DATE


def resolve_watched_at(value, release: date | datetime | None = None) -> datetime:
    """Turn a client `watched_at` value into an aware datetime; `release` is used for "release_date"."""
    if value in (None, '', WATCHED_AT_NOW):
        return timezone.now()
    if value == WATCHED_AT_UNKNOWN:
        return UNKNOWN_IMPORTED_DATE
    if value == WATCHED_AT_RELEASE_DATE:
        return _release_moment(release) or timezone.now()
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError({
            'watched_at': 'Must be "now", "unknown", "release_date", or an ISO 8601 timestamp.',
        }) from exc
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


def _release_moment(release: date | datetime | None) -> datetime | None:
    if release is None:
        return None
    if isinstance(release, datetime):
        return release if timezone.is_aware(release) else timezone.make_aware(release)
    return timezone.make_aware(datetime.combine(release, datetime.min.time()))
