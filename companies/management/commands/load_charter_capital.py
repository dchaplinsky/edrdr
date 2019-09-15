import sys
import argparse
from django.core.management.base import BaseCommand
from django.conf import settings
from csv import DictReader
from tqdm import tqdm
from dateutil.parser import parse as dt_parse

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
            if l["capital"]:
                capital = float(l["capital"])
            else:
                capital = None

            if l["reg_date"]:
                reg_date = dt_parse(l["reg_date"], yearfirst=True)
            else:
                reg_date = None

            CompanySnapshotFlags.objects.filter(company_id=edrpou).nocache().update(
                charter_capital=capital,
                reg_date=reg_date
            )
