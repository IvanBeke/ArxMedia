from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0027_repair_plan_to_watch_progress'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datatransferjob',
            name='source',
            field=models.CharField(
                choices=[
                    ('arxmedia', 'ArxMedia'),
                    ('trakt', 'Trakt'),
                    ('wetrakr', 'WeTrackr'),
                    ('yamtrack', 'Yamtrack'),
                ],
                default='arxmedia',
                max_length=20,
            ),
        ),
    ]
