from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0006_trakt_schedule_and_job_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='traktimportschedule',
            name='trakt_refresh_token',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='traktimportschedule',
            name='token_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='traktimportschedule',
            name='oauth_connected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
