# Generated by Django 2.1.7 on 2019-06-06 14:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0020_auto_20190606_1426'),
    ]

    operations = [
        migrations.RenameField(
            model_name='companysnapshotflags',
            old_name='has_bo_on_occupied_soild',
            new_name='has_bo_on_occupied_soil',
        ),
    ]
