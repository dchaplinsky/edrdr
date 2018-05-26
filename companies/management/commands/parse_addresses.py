from tqdm import tqdm
from django.core.management.base import BaseCommand
from django.db import transaction
from Levenshtein import distance
from multiprocessing import Pool

from companies.models import CompanyRecord
from companies.tools.address_parser import PyJsHoisted_getAddress_ as get_address


def parse_and_modify(rec):
    parsed = get_address(rec.location)

    if str(parsed["postalCode"]) != "undefined":
        rec.location_postal_code = str(parsed["postalCode"])
    if str(parsed["region"]) != "undefined":
        rec.location_region = str(parsed["region"])
    if str(parsed["district"]) != "undefined":
        rec.location_district = str(parsed["district"])
    if str(parsed["locality"]) != "undefined":
        rec.location_locality = str(parsed["locality"])
    if str(parsed["streetAddress"]) != "undefined":
        rec.location_street_address = str(parsed["streetAddress"])
    if str(parsed["apartment"]) != "undefined":
        rec.location_apartment = str(parsed["apartment"])

    rec.location_parsing_quality = distance(rec.location, str(parsed["fullAddress"]))
    return rec


class Command(BaseCommand):
    def handle(self, *args, **options):
        num = CompanyRecord.objects.count()
        rec_buffer = []
        my_tiny_pool = Pool(4)

        with tqdm(total=num) as pbar:
            for company_rec in CompanyRecord.objects.all().only(
                    "location", "location_postal_code", "location_region", "location_district",
                    "location_locality", "location_street_address", "location_apartment",
                    "location_parsing_quality").iterator():
                pbar.update(1)

                rec_buffer.append(company_rec)

                if len(rec_buffer) > 1000:
                    with transaction.atomic():
                        rec_buffer = list(
                            filter(
                                None,
                                my_tiny_pool.map(parse_and_modify, rec_buffer)
                            )
                        )

                        for r in rec_buffer:
                            r.save()
                    rec_buffer = []

            with transaction.atomic():
                rec_buffer = list(
                    filter(
                        None,
                        my_tiny_pool.map(parse_and_modify, rec_buffer)
                    )
                )

                for r in rec_buffer:
                    r.save()
