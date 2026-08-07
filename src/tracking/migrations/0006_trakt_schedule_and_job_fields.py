from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0005_listcollaborator_datatransferjob'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='datatransferjob',
            name='source',
            field=models.CharField(choices=[('local', 'Local file'), ('trakt', 'Trakt API')], default='local', max_length=20),
        ),
        migrations.AddField(
            model_name='datatransferjob',
            name='overwrite_existing',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='datatransferjob',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name='TraktImportSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trakt_username', models.CharField(max_length=150)),
                ('trakt_access_token', models.CharField(max_length=512)),
                ('cron_expression', models.CharField(default='0 3 * * *', max_length=100)),
                ('enabled', models.BooleanField(default=False)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trakt_import_schedule', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
