from django.db import migrations, models


def migrate_on_hold_to_watching(apps, schema_editor):
    WatchEntry = apps.get_model('tracking', 'WatchEntry')
    WatchEntry.objects.filter(status='on_hold').update(status='watching')


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0017_datatransferjob_import_mode'),
    ]

    operations = [
        migrations.RunPython(migrate_on_hold_to_watching, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='watchentry',
            name='status',
            field=models.CharField(
                choices=[
                    ('watched', 'Watched'),
                    ('watching', 'Watching'),
                    ('plan_to_watch', 'Plan to Watch'),
                    ('dropped', 'Dropped'),
                ],
                default='watched',
                max_length=20,
            ),
        ),
    ]
