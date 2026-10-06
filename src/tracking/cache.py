from django.core.cache import cache as django_cache

from .models import WatchEntry

STATS_TTL = 86400


class TrackingCache:
    def _key_stats(self, user_id):
        return f"user:{user_id}:stats"

    def get_user_stats(self, user_id):
        key = self._key_stats(user_id)
        stats = django_cache.get(key)
        if stats is None:
            stats = self._compute_user_stats(user_id)
            django_cache.set(key, stats, STATS_TTL)
        return stats

    def _compute_user_stats(self, user_id):
        from media.models import Episode, TVShow

        movies = WatchEntry.objects.for_user(user_id).movies().values('tmdb_id').distinct().count()

        episode_entries = WatchEntry.objects.for_user(user_id).episodes().values("tmdb_id").distinct()

        shows_watching = episode_entries.count()

        shows_completed = 0
        hours_watched = 0

        for entry in episode_entries:
            show = TVShow.objects.filter(tmdb_id=entry["tmdb_id"]).first()
            if not show:
                continue
            total_eps = Episode.objects.filter(
                season__show=show
            ).count()
            watched_eps = WatchEntry.objects.for_user(user_id).for_show(entry["tmdb_id"]).count()

            if total_eps and watched_eps >= total_eps:
                shows_completed += 1
                hours_watched += min(watched_eps, 10)

        return {
            "movies": movies,
            "shows_watching": shows_watching,
            "shows_completed": shows_completed,
            "hours": hours_watched,
        }

    def invalidate_user_stats(self, user_id):
        django_cache.delete(self._key_stats(user_id))


cache = TrackingCache()
