from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .choices import MediaType, WatchEntryMediaType
from .models import UserMediaStatus, WatchEntry
from .status_sync import refresh_show_status

_deleting_user_ids: set[int] = set()


@receiver(pre_delete, sender=get_user_model(), dispatch_uid='tracking_user_pre_delete_mark')
def mark_user_as_deleting(sender, instance, **kwargs):
    _deleting_user_ids.add(instance.id)


@receiver(post_delete, sender=get_user_model(), dispatch_uid='tracking_user_post_delete_unmark')
def unmark_user_as_deleting(sender, instance, **kwargs):
    _deleting_user_ids.discard(instance.id)


@receiver(post_save, sender=WatchEntry, dispatch_uid='tracking_watchentry_post_save_invalidate_cache')
def invalidate_watchentry_cache_on_save(sender, instance, **kwargs):
    from .cache import cache

    cache.invalidate_user_stats(instance.user_id)
    if instance.media_type == WatchEntryMediaType.MOVIE:
        watched_at = instance.watched_at or instance.created_at or timezone.now()
        UserMediaStatus.objects.update_or_create(
            user_id=instance.user_id,
            media_type=MediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
            defaults={
                'status': 'watched',
                'completed_at': watched_at,
                'last_watched_at': watched_at,
                'status_changed_at': watched_at,
                'progress_percent': 100,
            },
        )
    if instance.media_type == WatchEntryMediaType.EPISODE:
        cache.invalidate_show_progress(instance.user_id, instance.tmdb_id)
        refresh_show_status(instance.user_id, instance.tmdb_id)


@receiver(post_delete, sender=WatchEntry, dispatch_uid='tracking_watchentry_post_delete_invalidate_cache')
def invalidate_watchentry_cache_on_delete(sender, instance, **kwargs):
    if instance.user_id in _deleting_user_ids:
        return

    from .cache import cache

    cache.invalidate_user_stats(instance.user_id)
    if instance.media_type == WatchEntryMediaType.MOVIE:
        latest_movie_watch = WatchEntry.objects.filter(
            user_id=instance.user_id,
            media_type=WatchEntryMediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
        ).order_by('-watched_at', '-created_at', '-id').first()
        movie_status = UserMediaStatus.objects.filter(
            user_id=instance.user_id,
            media_type=MediaType.MOVIE,
            tmdb_id=instance.tmdb_id,
        ).first()
        if latest_movie_watch:
            watched_at = latest_movie_watch.watched_at or latest_movie_watch.created_at or timezone.now()
            UserMediaStatus.objects.update_or_create(
                user_id=instance.user_id,
                media_type=MediaType.MOVIE,
                tmdb_id=instance.tmdb_id,
                defaults={
                    'status': 'watched',
                    'completed_at': watched_at,
                    'last_watched_at': watched_at,
                    'status_changed_at': watched_at,
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
        cache.invalidate_show_progress(instance.user_id, instance.tmdb_id)
        refresh_show_status(instance.user_id, instance.tmdb_id)
