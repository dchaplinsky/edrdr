import sys
import argparse
from django.core.management.base import BaseCommand
from django.db import models
from companies.reports import GlobalStats

from tqdm import tqdm
from xlsxwriter import Workbook
from companies.models import Company


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "infile", nargs="?", type=argparse.FileType("r"), default=sys.stdin
        )
        parser.add_argument("outfile", type=argparse.FileType("wb"))
        parser.add_argument("--limit", type=int)

    def handle(self, *args, **options):
        gs = GlobalStats()
        ids = options["infile"]
        if options["limit"] is not None:
            ids = list(ids)[:options["limit"]]

        gs.write_bo_to_excel(options["outfile"], ids)
