from django.db import migrations

import tracking.fields


def encrypt_existing_tokens(apps, schema_editor):
    TraktImportSchedule = apps.get_model('tracking', 'TraktImportSchedule')
    for schedule in TraktImportSchedule.objects.all().iterator():
        schedule.save(update_fields=['trakt_access_token', 'trakt_refresh_token', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0007_trakt_oauth_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='traktimportschedule',
            name='trakt_access_token',
            field=tracking.fields.EncryptedText(),
        ),
        migrations.AlterField(
            model_name='traktimportschedule',
            name='trakt_refresh_token',
            field=tracking.fields.EncryptedText(blank=True),
        ),
        migrations.RunPython(encrypt_existing_tokens, migrations.RunPython.noop),
    ]
