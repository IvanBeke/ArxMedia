import threading
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.db.models import F
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .choices import MediaType, WatchEntryMediaType
from .models import UserMediaStatus, WatchEntry
from .status_sync import refresh_show_status

_deleting_user_ids: set[int] = set()
_suppress_state = threading.local()


@contextmanager
def suppress_watch_entry_delete_signals():
    """Skip per-row delete handling; the caller refreshes status once afterwards."""
    previous = getattr(_suppress_state, 'active', False)
    _suppress_state.active = True
    try:
        yield
    finally:
        _suppress_state.active = previous


@receiver(pre_delete, sender=get_user_model(), dispatch_uid='tracking_user_pre_delete_mark')
def mark_user_as_deleting(sender, instance, **kwargs):
    _deleting_user_ids.add(instance.id)


@receiver(post_delete, sender=get_user_model(), dispatch_uid='tracking_user_post_delete_unmark')
def unmark_user_as_deleting(sender, instance, **kwargs):
    _deleting_user_ids.discard(instance.id)


@receiver(post_save, sender=WatchEntry, dispatch_uid='tracking_watchentry_post_save_sync_status')
def sync_media_status_on_save(sender, instance, **kwargs):
    if instance.media_type == WatchEntryMediaType.MOVIE:
        watched_at = instance.watched_at
        UserMediaStatus.objects.update_or_create(
            user_id=instance.user_id,
            media_type=MediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
            defaults={
                'status': 'watched',
                'completed_at': watched_at,
                'last_watched_at': watched_at,
                'status_changed_at': watched_at or timezone.now(),
                'progress_percent': 100,
            },
        )
    if instance.media_type == WatchEntryMediaType.EPISODE:
        refresh_show_status(instance.user_id, instance.tmdb_id)


@receiver(post_delete, sender=WatchEntry, dispatch_uid='tracking_watchentry_post_delete_sync_status')
def sync_media_status_on_delete(sender, instance, **kwargs):
    if instance.user_id in _deleting_user_ids or getattr(_suppress_state, 'active', False):
        return

    if instance.media_type == WatchEntryMediaType.MOVIE:
        latest_movie_watch = WatchEntry.objects.filter(
            user_id=instance.user_id,
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
        ).order_by(F('watched_at').desc(nulls_last=True), '-created_at', '-id').first()
        movie_status = UserMediaStatus.objects.filter(
            user_id=instance.user_id,
            media_type=MediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
        ).first()
        if latest_movie_watch:
            watched_at = latest_movie_watch.watched_at
            UserMediaStatus.objects.update_or_create(
                user_id=instance.user_id,
                media_type=MediaType.MOVIE,
                tmdb_id=instance.tmdb_id,
                defaults={
                    'status': 'watched',
                    'completed_at': watched_at,
                    'last_watched_at': watched_at,
                    'status_changed_at': watched_at or timezone.now(),
                    'progress_percent': 100,
                },
            )
        elif movie_status and movie_status.status == 'plan_to_watch':
            pass
        else:
            UserMediaStatus.objects.filter(
                user_id=instance.user_id,
                media_type=MediaType.MOVIE,
                tmdb_id=instance.tmdb_id,
            ).delete()
    if instance.media_type == WatchEntryMediaType.EPISODE:
        refresh_show_status(instance.user_id, instance.tmdb_id)
