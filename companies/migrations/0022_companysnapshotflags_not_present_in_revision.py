# Generated by Django 2.1.7 on 2019-06-06 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0021_auto_20190606_1434'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysnapshotflags',
            name='not_present_in_revision',
            field=models.BooleanField(default=False),
        ),
    ]
