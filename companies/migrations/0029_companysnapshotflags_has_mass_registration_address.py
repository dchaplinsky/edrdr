# Generated by Django 2.1.7 on 2019-06-12 14:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0028_auto_20190612_1331'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysnapshotflags',
            name='has_mass_registration_address',
            field=models.BooleanField(default=False),
        ),
    ]