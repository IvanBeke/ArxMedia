from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0015_rework_list_privacy'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datatransferjob',
            name='source',
            field=models.CharField(
                choices=[('arxmedia', 'ArxMedia'), ('trakt', 'Trakt'), ('yamtrack', 'Yamtrack')],
                default='arxmedia',
                max_length=20,
            ),
        ),
    ]
