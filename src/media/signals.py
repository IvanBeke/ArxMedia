import threading
from contextlib import contextmanager

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Episode

_suppress_state = threading.local()


def _signals_suppressed() -> bool:
    return bool(getattr(_suppress_state, 'active', False))


def episode_signals_suppressed() -> bool:
    """True while a bulk TV sync owns the terminal rebuild/refresh."""
    return _signals_suppressed()


@contextmanager
def suppress_episode_signals():
    """Suppress per-episode status rebuilds during bulk TV sync.

    sync_tv_show performs its own single terminal rebuild/refresh, so
    firing a full chain rebuild + status refresh per episode save is
    pure overhead (full episode table scan + aggregates per episode).
    """
    previous = getattr(_suppress_state, 'active', False)
    _suppress_state.active = True
    try:
        yield
    finally:
        _suppress_state.active = previous


def _refresh_episode_show(instance):
    from tracking.status_sync import rebuild_episode_chain, refresh_all_statuses_for_show

    tmdb_id = instance.season.show.tmdb_id
    rebuild_episode_chain(tmdb_id)
    refresh_all_statuses_for_show(tmdb_id)


@receiver(post_save, sender=Episode, dispatch_uid='media_episode_refresh_show_status')
def refresh_status_after_episode_save(sender, instance, **kwargs):
    if _signals_suppressed():
        return
    _refresh_episode_show(instance)


@receiver(post_delete, sender=Episode, dispatch_uid='media_episode_refresh_show_status_delete')
def refresh_status_after_episode_delete(sender, instance, **kwargs):
    if _signals_suppressed():
        return
    _refresh_episode_show(instance)
