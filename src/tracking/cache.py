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
        from .choices import TvShowStatus
        from .models import UserMediaStatus

        watched = WatchEntry.objects.for_user(user_id)
        return {
            "movies": watched.movies().values('tmdb_id').distinct().count(),
            "shows_watching": watched.episodes().values('tmdb_id').distinct().count(),
            "shows_completed": UserMediaStatus.objects.for_user(user_id).shows().filter(status=TvShowStatus.WATCHED).count(),
        }

    def invalidate_user_stats(self, user_id):
        django_cache.delete(self._key_stats(user_id))


cache = TrackingCache()
