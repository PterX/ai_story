from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('models', '0004_add_user_api_token'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserApiToken',
        ),
    ]
