import sys
import argparse
from django.core.management.base import BaseCommand
from django.conf import settings
from csv import DictReader
from tqdm import tqdm

from companies.models import CompanySnapshotFlags


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


        for l in tqdm(reader):
            edrpou = l["code"].strip().lstrip("0")
            if not edrpou or not edrpou.isdigit():
                print("Cannot identify company by edrpou {}, pep line was {}".format(edrpou, l))
                continue
            
            edrpou = int(edrpou)
            capital = float(l["capital"])

            if capital > 0:
                CompanySnapshotFlags.objects.filter(company_id=edrpou).update(charter_capital=capital)
