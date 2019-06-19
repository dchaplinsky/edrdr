# Generated by Django 2.1.7 on 2019-06-06 14:11

import django.contrib.postgres.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0018_person_was_dereferenced'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanySnapshotFlags',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('has_bo', models.BooleanField(default=False)),
                ('has_bo_persons', models.BooleanField(default=False)),
                ('has_bo_companies', models.BooleanField(default=False)),
                ('has_dereferenced_bo', models.BooleanField(default=False)),
                ('has_only_persons_bo', models.BooleanField(default=False)),
                ('has_only_companies_bo', models.BooleanField(default=False)),
                ('has_founder_persons', models.BooleanField(default=False)),
                ('has_founder_companies', models.BooleanField(default=False)),
                ('has_only_persons_founder', models.BooleanField(default=False)),
                ('has_only_companies_founder', models.BooleanField(default=False)),
                ('all_founder_persons', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), default=list, size=None, verbose_name='Усі засновники ФО')),
                ('all_owner_persons', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), default=list, size=None, verbose_name='Усі бенефіціарні власники ФО')),
                ('has_same_person_as_bo_and_founder', models.BooleanField(default=False)),
                ('has_same_person_as_bo_and_head', models.BooleanField(default=False)),
                ('has_very_similar_person_as_bo_and_founder', models.BooleanField(default=False)),
                ('has_very_similar_as_bo_and_head', models.BooleanField(default=False)),
                ('all_similar_founders_and_bos', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='Результати порівняння бенефіціарів та власників')),
                ('all_similar_heads_and_bos', django.contrib.postgres.fields.jsonb.JSONField(default=dict, verbose_name='Результати порівняння бенефіціарів та директорів')),
                ('all_bo_countries', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), default=list, size=None, verbose_name="Усі країни окрім України, до яких прив'язані БО")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshot_stats', to='companies.Company', verbose_name='Компанія')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshot_stats', to='companies.Revision', verbose_name='Ревізія')),
            ],
        ),
    ]