# Generated by Django 2.1.7 on 2019-06-11 13:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0025_person_bo_is_absent'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyrecord',
            name='parsed_location',
            field=models.TextField(blank=True, verbose_name='Адреса реєстрації (уніфікована)'),
        ),
        migrations.AddField(
            model_name='companyrecord',
            name='shortened_validated_location',
            field=models.TextField(blank=True, verbose_name='Адреса реєстрації (після верифікації за реєстром та без району)'),
        ),
        migrations.AddField(
            model_name='companyrecord',
            name='validated_location',
            field=models.TextField(blank=True, verbose_name='Адреса реєстрації (після верифікації за реєстром)'),
        ),
    ]
