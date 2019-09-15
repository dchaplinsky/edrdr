# Generated by Django 2.2.3 on 2019-09-01 14:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0040_companysnapshotflags_charter_capital'),
    ]

    operations = [
        migrations.CreateModel(
            name='OwnedByCompany',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(blank=True, default='', verbose_name='Опис власника')),
                ('owner', models.CharField(blank=True, default='', max_length=200, verbose_name='Власник (код)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_by_company', to='companies.Company', verbose_name='Компанія')),
            ],
        ),
    ]
