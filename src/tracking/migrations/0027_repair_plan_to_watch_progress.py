from django.db import migrations
from django.db.models import Q


def repair_plan_to_watch_progress(apps, schema_editor):
    from django.utils import timezone

    Episode = apps.get_model('media', 'Episode')
    UserMediaStatus = apps.get_model('tracking', 'UserMediaStatus')
    WatchEntry = apps.get_model('tracking', 'WatchEntry')

    now = timezone.now()
    released_q = Q(season__season_number__gt=0) & (
        Q(broadcast_start__lte=now)
        | Q(broadcast_start__isnull=True, air_date__lte=now.date())
    )
    episode_rows = {}
    for row in Episode.objects.filter(season__show__tmdb_id__isnull=False).filter(released_q).values(
        'season__show__tmdb_id', 'season__season_number', 'episode_number', 'runtime',
    ).iterator():
        episode_rows.setdefault(row['season__show__tmdb_id'], []).append(row)

    statuses = UserMediaStatus.objects.filter(media_type='tv', status='plan_to_watch')
    watched_rows = WatchEntry.objects.filter(media_type='episode', season_number__gt=0).values(
        'user_id', 'tmdb_id', 'season_number', 'episode_number',
    ).distinct().iterator()
    watched_keys = {}
    for row in watched_rows:
        watched_keys.setdefault((row['user_id'], row['tmdb_id']), set()).add(
            (row['season_number'], row['episode_number'])
        )

    updates = []
    for status in statuses.iterator(chunk_size=500):
        released = episode_rows.get(status.tmdb_id, [])
        released_keys = {(row['season__season_number'], row['episode_number']) for row in released}
        watched = watched_keys.get((status.user_id, status.tmdb_id), set()) & released_keys
        remaining = [
            row for row in released
            if (row['season__season_number'], row['episode_number']) not in watched
        ]
        total = len(released)
        watched_count = len(watched)
        values = {
            'watched_episodes': watched_count,
            'total_episodes': total,
            'progress_percent': min(100, watched_count * 100 // total) if total else 0,
            'episodes_left': len(remaining),
            'time_left_minutes': sum(row['runtime'] for row in remaining if row['runtime'] is not None),
            'time_left_has_unknown': any(row['runtime'] is None for row in remaining),
            'started_at': None,
            'last_watched_at': None,
            'completed_at': None,
        }
        if any(getattr(status, field) != value for field, value in values.items()):
            for field, value in values.items():
                setattr(status, field, value)
            updates.append(status)
        if len(updates) >= 500:
            UserMediaStatus.objects.bulk_update(
                updates,
                [*values, 'updated_at'],
                batch_size=500,
            )
            updates.clear()

    if updates:
        UserMediaStatus.objects.bulk_update(
            updates,
            [*values, 'updated_at'],
            batch_size=500,
        )


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ('tracking', '0026_repair_tv_progress'),
    ]

    operations = [migrations.RunPython(repair_plan_to_watch_progress, migrations.RunPython.noop)]  # noqa: RUF012
