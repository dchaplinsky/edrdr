# Generated by Django 2.0.4 on 2018-06-02 09:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0012_company_is_dirty'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='person_type',
            field=models.CharField(choices=[('head', 'Голова'), ('founder', 'Засновник'), ('owner', 'Бенефіціарний власник')], db_index=True, max_length=10),
        ),
    ]