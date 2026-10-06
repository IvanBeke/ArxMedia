from django.conf import settings
from django.db import migrations, models
from django.db.models import Count, F


def remove_duplicate_episode_entries(apps, schema_editor):
    WatchEntry = apps.get_model('tracking', 'WatchEntry')
    key = ('user_id', 'tmdb_id', 'season_number', 'episode_number')
    groups = (
        WatchEntry.objects.filter(media_type='episode')
        .values(*key)
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    for group in groups.iterator():
        rows = WatchEntry.objects.filter(media_type='episode', **{field: group[field] for field in key})
        keeper = rows.order_by(F('watched_at').asc(nulls_last=True), 'id').values_list('id', flat=True).first()
        rows.exclude(id=keeper).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0029_private_data_transfer_paths'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_episode_entries, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='watchentry',
            constraint=models.UniqueConstraint(
                condition=models.Q(('media_type', 'episode')),
                fields=('user', 'tmdb_id', 'season_number', 'episode_number'),
                name='unique_user_episode_watch',
            ),
        ),
    ]
