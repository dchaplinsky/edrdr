# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-02-10 13:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyrecord',
            name='company_hash',
            field=models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Ключ дедуплікації'),
        ),
    ]
