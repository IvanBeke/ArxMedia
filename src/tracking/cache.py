import json

import redis
from django.conf import settings

from .choices import WatchEntryMediaType
from .models import WatchEntry


class TrackingCache:
    def __init__(self):
        self._redis = None
        self._enabled = bool(getattr(settings, "REDIS_URL", None))

    def _get_redis(self):
        if self._redis is None:
            url = getattr(settings, "REDIS_URL", None)
            if url:
                self._redis = redis.from_url(url, decode_responses=True)
        return self._redis

    def _key_stats(self, user_id):
        return f"user:{user_id}:stats"

    def _key_show_progress(self, user_id, tmdb_id):
        return f"user:{user_id}:show:{tmdb_id}:progress"

    def _key_episode_watched(self, user_id, tmdb_id):
        return f"user:{user_id}:episode:{tmdb_id}:watched"

    def get_user_stats(self, user_id):
        r = self._get_redis()
        if not r:
            return self._compute_user_stats(user_id)

        key = self._key_stats(user_id)
        cached = r.get(key)
        if cached:
            return json.loads(cached)

        stats = self._compute_user_stats(user_id)
        r.setex(key, 86400, json.dumps(stats))
        return stats

    def _compute_user_stats(self, user_id):
        from media.models import Episode, TVShow

        movies = WatchEntry.objects.filter(user_id=user_id, media_type=WatchEntryMediaType.MOVIE).count()

        episode_entries = WatchEntry.objects.filter(
            user_id=user_id, media_type=WatchEntryMediaType.EPISODE
        ).values("tmdb_id").distinct()

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
            watched_eps = WatchEntry.objects.filter(
                user_id=user_id, media_type=WatchEntryMediaType.EPISODE, tmdb_id=entry["tmdb_id"]
            ).count()

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
        r = self._get_redis()
        if r:
            r.delete(self._key_stats(user_id))

    def get_show_progress(self, user_id, tmdb_id):
        r = self._get_redis()
        if not r:
            return self._compute_show_progress(user_id, tmdb_id)

        key = self._key_show_progress(user_id, tmdb_id)
        cached = r.get(key)
        if cached:
            return json.loads(cached)

        progress = self._compute_show_progress(user_id, tmdb_id)
        r.setex(key, 86400, json.dumps(progress))
        return progress

    def _compute_show_progress(self, user_id, tmdb_id):
        from media.models import Episode, TVShow

        watched = list(
            WatchEntry.objects.filter(
                user_id=user_id, media_type=WatchEntryMediaType.EPISODE, tmdb_id=tmdb_id
            ).values("season_number", "episode_number").order_by(
                "season_number", "episode_number"
            )
        )

        if not watched:
            return {"season": None, "episode": None, "watched": 0, "total": 0}

        show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
        total = Episode.objects.filter(season__show=show).count() if show else 0

        last = watched[-1]
        return {
            "season": last["season_number"],
            "episode": last["episode_number"],
            "watched": len(watched),
            "total": total,
        }

    def invalidate_show_progress(self, user_id, tmdb_id):
        r = self._get_redis()
        if r:
            r.delete(self._key_show_progress(user_id, tmdb_id))
            r.delete(self._key_episode_watched(user_id, tmdb_id))

    def mark_episode_watched(self, user_id, tmdb_id, season_number, episode_number):
        r = self._get_redis()
        if r:
            key = self._key_episode_watched(user_id, tmdb_id)
            r.sadd(key, f"{season_number}:{episode_number}")

    def unmark_episode_watched(self, user_id, tmdb_id, season_number, episode_number):
        r = self._get_redis()
        if r:
            key = self._key_episode_watched(user_id, tmdb_id)
            r.srem(key, f"{season_number}:{episode_number}")


cache = TrackingCache()
