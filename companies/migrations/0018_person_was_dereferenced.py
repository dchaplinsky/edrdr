# Generated by Django 2.1.7 on 2019-06-05 22:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0017_auto_20190106_1416'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='was_dereferenced',
            field=models.BooleanField(default=False),
        ),
    ]
