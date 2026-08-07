from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0004_remove_show_and_progress_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DataTransferJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_type', models.CharField(choices=[('import', 'Import'), ('export', 'Export')], max_length=10)),
                ('data_format', models.CharField(choices=[('json', 'JSON'), ('csv', 'CSV')], max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('input_file', models.FileField(blank=True, null=True, upload_to='imports/')),
                ('output_file', models.FileField(blank=True, null=True, upload_to='exports/')),
                ('total_items', models.IntegerField(default=0)),
                ('processed_items', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ListCollaborator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('custom_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaboratorships', to='tracking.customlist')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='list_collaborations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('custom_list', 'user')},
            },
        ),
    ]
