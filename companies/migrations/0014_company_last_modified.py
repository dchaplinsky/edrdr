# Generated by Django 2.0.4 on 2018-06-08 14:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0013_auto_20180602_0913'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
