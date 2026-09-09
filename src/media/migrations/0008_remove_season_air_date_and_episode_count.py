from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('media', '0007_episode_broadcast_start_episode_external_ids_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='season',
            name='air_date',
        ),
        migrations.RemoveField(
            model_name='season',
            name='episode_count',
        ),
    ]
