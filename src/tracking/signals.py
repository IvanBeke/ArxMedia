from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .choices import MediaType, WatchEntryMediaType
from .models import WatchEntry, Watchlist
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
    if instance.media_type == WatchEntryMediaType.EPISODE:
        cache.invalidate_show_progress(instance.user_id, instance.tmdb_id)
        refresh_show_status(instance.user_id, instance.tmdb_id)


@receiver(post_delete, sender=WatchEntry, dispatch_uid='tracking_watchentry_post_delete_invalidate_cache')
def invalidate_watchentry_cache_on_delete(sender, instance, **kwargs):
    if instance.user_id in _deleting_user_ids:
        return

    from .cache import cache

    cache.invalidate_user_stats(instance.user_id)
    if instance.media_type == WatchEntryMediaType.EPISODE:
        cache.invalidate_show_progress(instance.user_id, instance.tmdb_id)
        refresh_show_status(instance.user_id, instance.tmdb_id)


@receiver(post_save, sender=Watchlist, dispatch_uid='tracking_watchlist_post_save_refresh_status')
def refresh_watchlist_status_on_save(sender, instance, **kwargs):
    if instance.media_type == MediaType.TV:
        refresh_show_status(instance.user_id, instance.tmdb_id)


@receiver(post_delete, sender=Watchlist, dispatch_uid='tracking_watchlist_post_delete_refresh_status')
def refresh_watchlist_status_on_delete(sender, instance, **kwargs):
    if instance.user_id in _deleting_user_ids:
        return

    if instance.media_type == MediaType.TV:
        refresh_show_status(instance.user_id, instance.tmdb_id)
