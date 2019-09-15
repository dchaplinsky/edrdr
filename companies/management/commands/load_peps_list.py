import sys
import argparse
from django.core.management.base import BaseCommand
from django.conf import settings
from csv import DictReader
from tqdm import tqdm

from companies.models import PEPOwner, Company


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "in_file",
            type=argparse.FileType("r"),
            default=sys.stdout,
            help="Input file to load",
        )

    def handle(self, *args, **options):
        reader = DictReader(options["in_file"])

        PEPOwner.objects.all().delete()

        for l in tqdm(reader):
            if not l["edrpou"]:
                continue
            edrpou = l["edrpou"].strip().lstrip("0")
            if not edrpou or not edrpou.isdigit():
                print("Cannot identify company by edrpou {}, pep line was {}".format(edrpou, l))
                continue
            
            edrpou = int(edrpou)

            company = Company.objects.filter(pk=edrpou).first()

            if company is None:
                print("Cannot find company {} in db, pep line was {}".format(edrpou, l))
                continue

            pep = PEPOwner(
                years=list(map(int, filter(None, l["years"].split(", ")))),
                person=l["pep"],
                person_url=l["url"],
                from_declaration=l["from_declaration"] == "True",
                company=company,
                person_type=l.get("person_type", "owner")
            )

            pep.save()
