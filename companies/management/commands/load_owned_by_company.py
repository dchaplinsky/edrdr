import sys
import argparse
from django.core.management.base import BaseCommand
from django.conf import settings
from csv import DictReader
from tqdm import tqdm

from companies.models import OwnedByCompany, Company


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

        OwnedByCompany.objects.all().delete()

        for l in tqdm(reader):
            edrpou = l["edrpou"].strip().lstrip("0")
            company = Company.objects.filter(pk=edrpou).first()

            if company is None:
                print("Cannot find company {} in db, owner line was {}".format(edrpou, l))
                continue

            owner = OwnedByCompany(
                company=company,
                description=l["description"],
                owner=l["owner"]
            )

            owner.save()
