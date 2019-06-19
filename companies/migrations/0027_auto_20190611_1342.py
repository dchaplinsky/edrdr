# Generated by Django 2.1.7 on 2019-06-11 13:42

from tqdm import tqdm
from django.db import migrations


def get_parsed_location(rec):
    return ", ".join(
        filter(
            None,
            [
                rec.location_postal_code,
                rec.location_region,
                rec.location_district,
                rec.location_locality,
                rec.location_street_address,
                rec.location_apartment,
            ],
        )
    )

def get_validated_location(rec):
    return ", ".join(
        filter(
            None,
            [
                rec.validated_location_postal_code,
                rec.validated_location_region,
                rec.validated_location_district,
                rec.validated_location_locality,
                rec.validated_location_street_address,
                rec.validated_location_apartment,
            ],
        )
    )

def get_shortened_validated_location(rec):
    return ", ".join(
        filter(
            None,
            [
                rec.validated_location_postal_code,
                rec.validated_location_region,
                rec.validated_location_street_address,
                rec.validated_location_apartment,
            ],
        )
    )

def cache_parsed_addresses(apps, schema_editor):
    CompanyRecord = apps.get_model("companies", "CompanyRecord")
    qs = CompanyRecord.objects.nocache()

    for rec in tqdm(qs.iterator(), total=qs.count()):
        rec.parsed_location = get_parsed_location(rec)
        rec.validated_location = get_validated_location(rec)
        rec.shortened_validated_location = get_shortened_validated_location(rec)
        rec.save()

class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0026_auto_20190611_1338'),
    ]

    operations = [
        migrations.RunPython(cache_parsed_addresses, reverse_code=migrations.RunPython.noop)
    ]