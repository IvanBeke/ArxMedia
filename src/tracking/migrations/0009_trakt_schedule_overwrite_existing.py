from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0008_encrypt_trakt_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='traktimportschedule',
            name='overwrite_existing',
            field=models.BooleanField(default=True),
        ),
    ]
