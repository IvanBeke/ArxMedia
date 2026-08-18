from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media', '0004_episode_vote_count_episodecredit'),
    ]

    operations = [
        migrations.AddField(
            model_name='tvshow',
            name='episode_runtime',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
