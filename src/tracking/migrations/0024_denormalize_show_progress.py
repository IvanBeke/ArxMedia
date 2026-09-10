from django.db import migrations, models
from django.db.models import Q


def rebuild_episode_chains(apps, schema_editor):
    Episode = apps.get_model('media', 'Episode')
    TVShow = apps.get_model('media', 'TVShow')
    UserMediaStatus = apps.get_model('tracking', 'UserMediaStatus')
    WatchEntry = apps.get_model('tracking', 'WatchEntry')
    from django.utils import timezone

    now = timezone.now()
    today = now.date()
    for show in TVShow.objects.all().iterator():
        episodes = list(Episode.objects.filter(season__show_id=show.id).order_by(
            'season__season_number', 'episode_number', 'id'
        ))
        for index, episode in enumerate(episodes):
            episode.next_episode_id = episodes[index + 1].id if index + 1 < len(episodes) else None
        Episode.objects.bulk_update(episodes, ['next_episode'])

        released = list(Episode.objects.filter(
            season__show_id=show.id,
            season__season_number__gt=0,
        ).filter(
            Q(broadcast_start__lte=now)
            | Q(broadcast_start__isnull=True, air_date__lte=today)
        ).values('id', 'season__season_number', 'episode_number', 'runtime'))
        for status_row in UserMediaStatus.objects.filter(media_type='tv', tmdb_id=show.tmdb_id).exclude(status='plan_to_watch').iterator():
            watched_keys = set(WatchEntry.objects.filter(
                user_id=status_row.user_id,
                media_type='episode',
                tmdb_id=show.tmdb_id,
                season_number__gt=0,
            ).values_list('season_number', 'episode_number'))
            remaining = [
                row for row in released
                if (row['season__season_number'], row['episode_number']) not in watched_keys
            ]
            next_id = remaining[0]['id'] if remaining else None
            known_runtime = sum(row['runtime'] for row in remaining if row['runtime'] is not None)
            status_row.watched_episodes = len(watched_keys)
            status_row.total_episodes = len(released)
            status_row.progress_percent = (
                min(100, status_row.watched_episodes * 100 // len(released)) if released else 0
            )
            status_row.episodes_left = len(remaining)
            status_row.time_left_minutes = known_runtime
            status_row.time_left_has_unknown = any(row['runtime'] is None for row in remaining)
            status_row.next_episode_id = next_id
            status_row.save(update_fields=[
                'watched_episodes', 'total_episodes', 'progress_percent',
                'episodes_left', 'time_left_minutes', 'time_left_has_unknown', 'next_episode',
            ])


class Migration(migrations.Migration):
    dependencies = [
        ('media', '0009_episode_next_episode'),
        ('tracking', '0023_alter_datatransferjob_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermediastatus',
            name='episodes_left',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='usermediastatus',
            name='time_left_minutes',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='usermediastatus',
            name='time_left_has_unknown',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usermediastatus',
            name='next_episode',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='+',
                to='media.episode',
            ),
        ),
        migrations.RunPython(rebuild_episode_chains, migrations.RunPython.noop),
    ]
