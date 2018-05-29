from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

from Levenshtein import distance
from tqdm import tqdm
from multiprocessing import Pool

from companies.models import CompanyRecord
from companies.tools.address_parser import PyJsHoisted_getAddress_ as get_address
from companies.elastic_models import Address


def parse_and_modify(rec):
    parsed = get_address(rec.location)

    mapping = {
        "postalCode": "location_postal_code",
        "region": "location_region",
        "district": "location_district",
        "locality": "location_locality",
        "streetAddress": "location_street_address",
        "apartment": "location_apartment"
    }

    # Replacing fucking JS wrapper with native dict
    parsed = {k.to_py(): parsed[k].to_py() for k in parsed}

    rec.location_parsing_quality = distance(
        rec.location.lower(),
        parsed["fullAddress"].lower()
    )

    validated_mapping = {
        "postalCode": "validated_location_postal_code",
        "region": "validated_location_region",
        "district": "validated_location_district",
        "locality": "validated_location_locality",
        "streetAddress": "validated_location_street_address",
        "apartment": "validated_location_apartment"
    }

    validated_address = Address.validate(parsed)

    if "streetNumber" in parsed:
        parsed["streetAddress"] += ', ' + parsed["streetNumber"]

    for k, v in mapping.items():
        if parsed.get(k) is None:
            parsed[k] = ""
        setattr(rec, v, parsed[k])

    for k, v in validated_mapping.items():
        if validated_address.get(k) is None:
            validated_address[k] = ""
        setattr(rec, v, validated_address[k])

    return rec


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--parse_all',
            action='store_true',
            dest='parse_all',
            default=False,
            help='Parse all records again (slow!)',
        )

    def write_to_db(self, rec_buffer):
        with transaction.atomic():
            for r in rec_buffer:
                r.save()

    def handle(self, *args, **options):
        rec_buffer = []
        my_tiny_pool = Pool(settings.NUM_THREADS)

        if options["parse_all"]:
            qs = CompanyRecord.objects.all()
        else:
            qs = CompanyRecord.objects.filter(
                company__is_dirty=True
            )

        with tqdm(total=qs.count()) as pbar:
            for company_rec in qs.only(
                    "location", "location_postal_code", "location_region", "location_district",
                    "location_locality", "location_street_address", "location_apartment",
                    "location_parsing_quality", "validated_location_postal_code",
                    "validated_location_region", "validated_location_district",
                    "validated_location_locality", "validated_location_street_address",
                    "validated_location_apartment").iterator():
                pbar.update(1)

                rec_buffer.append(company_rec)

                if len(rec_buffer) > settings.NUM_THREADS * 100:
                    rec_buffer = list(
                        filter(
                            None,
                            my_tiny_pool.map(parse_and_modify, rec_buffer)
                        )
                    )

                    self.write_to_db(rec_buffer)
                    rec_buffer = []

            rec_buffer = list(
                filter(
                    None,
                    my_tiny_pool.map(parse_and_modify, rec_buffer)
                )
            )

            self.write_to_db(rec_buffer)
