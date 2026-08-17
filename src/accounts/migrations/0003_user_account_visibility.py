from django.db import migrations, models


def _copy_visibility_forward(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all().only('id', 'is_private'):
        user.account_visibility = 'private' if user.is_private else 'public'
        user.save(update_fields=['account_visibility'])


def _copy_visibility_backward(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all().only('id', 'account_visibility'):
        user.is_private = user.account_visibility == 'private'
        user.save(update_fields=['is_private'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_user_preferred_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='account_visibility',
            field=models.CharField(
                choices=[('public', 'Public'), ('private', 'Private'), ('friends_only', 'Friends only')],
                default='public',
                max_length=20,
            ),
        ),
        migrations.RunPython(_copy_visibility_forward, _copy_visibility_backward),
        migrations.RemoveField(
            model_name='user',
            name='is_private',
        ),
    ]
