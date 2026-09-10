from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('tracking', '0024_denormalize_show_progress'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='usermediastatus',
            name='next_episode',
        ),
    ]
