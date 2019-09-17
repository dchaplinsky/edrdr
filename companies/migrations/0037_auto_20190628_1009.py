# Generated by Django 2.2.2 on 2019-06-28 10:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0036_auto_20190627_1213'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysnapshotflags',
            name='had_pep_owner_in_the_past',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companysnapshotflags',
            name='has_discrepancy_with_declarations',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companysnapshotflags',
            name='has_pep_owner',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='companysnapshotflags',
            name='has_undeclared_pep_owner',
            field=models.BooleanField(default=False),
        ),
    ]