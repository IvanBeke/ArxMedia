from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0009_trakt_schedule_overwrite_existing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datatransferjob',
            name='data_format',
            field=models.CharField(choices=[('json', 'JSON'), ('csv', 'CSV'), ('zip', 'ZIP')], max_length=10),
        ),
    ]
