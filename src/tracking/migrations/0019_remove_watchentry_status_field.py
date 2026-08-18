from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0018_remove_on_hold_watch_entry_status'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='watchentry',
            name='tracking_wa_user_id_fc718d_idx',
        ),
        migrations.RemoveIndex(
            model_name='watchentry',
            name='tracking_wa_user_id_863851_idx',
        ),
        migrations.RemoveField(
            model_name='watchentry',
            name='status',
        ),
    ]
