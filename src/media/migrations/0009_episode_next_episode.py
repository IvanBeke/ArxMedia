from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('media', '0008_remove_season_air_date_and_episode_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='episode',
            name='next_episode',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='previous_episodes',
                to='media.episode',
            ),
        ),
    ]
