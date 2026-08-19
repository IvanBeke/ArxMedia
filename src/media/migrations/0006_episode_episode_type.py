from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media', '0005_tvshow_episode_runtime'),
    ]

    operations = [
        migrations.AddField(
            model_name='episode',
            name='episode_type',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
