# Generated by Django 2.2.2 on 2019-06-16 11:33

from django.db import migrations
from tqdm import tqdm


def filter_and_cleanup(list_of_countries):
    return list(
        set(
            filter(
                lambda x: x not in ["пряме", "прямий", "республіка", "причина", "флорида", "лакатамія"],
                map(str.strip, list_of_countries),
            )
        )
    )


def cleanup_countries(apps, schema_editor):
    Person = apps.get_model("companies", "Person")
    qs = Person.objects.exclude(country__len=0).nocache()

    for rec in tqdm(qs.iterator(), total=qs.count()):
        rec.country = filter_and_cleanup(rec.country)
        rec.save()


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0030_auto_20190613_1553'),
    ]

    operations = [
        migrations.RunPython(cleanup_countries, reverse_code=migrations.RunPython.noop)
    ]