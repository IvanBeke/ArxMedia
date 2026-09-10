from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Episode


def _refresh_episode_show(instance):
    from tracking.status_sync import rebuild_episode_chain, refresh_all_statuses_for_show

    tmdb_id = instance.season.show.tmdb_id
    rebuild_episode_chain(tmdb_id)
    refresh_all_statuses_for_show(tmdb_id)


@receiver(post_save, sender=Episode, dispatch_uid='media_episode_refresh_show_status')
def refresh_status_after_episode_save(sender, instance, **kwargs):
    _refresh_episode_show(instance)


@receiver(post_delete, sender=Episode, dispatch_uid='media_episode_refresh_show_status_delete')
def refresh_status_after_episode_delete(sender, instance, **kwargs):
    _refresh_episode_show(instance)
