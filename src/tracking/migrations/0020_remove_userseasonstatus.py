from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0019_remove_watchentry_status_field'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserSeasonStatus',
        ),
    ]
