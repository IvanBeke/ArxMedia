from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0016_alter_datatransferjob_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='datatransferjob',
            name='import_mode',
            field=models.CharField(
                choices=[
                    ('new_items', 'New Items'),
                    ('update_existing', 'Update Existing'),
                    ('mirror_imported_set', 'Mirror Imported Set'),
                ],
                default='new_items',
                max_length=32,
            ),
        ),
    ]
