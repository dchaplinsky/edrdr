import sys
import argparse
from django.core.management.base import BaseCommand
from tqdm import tqdm
from companies.models import Person


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)

    def handle(self, *args, **options):
        rec_buffer = []
    
        for p_names in tqdm(
            Person.objects.all().nocache().values_list("name", flat=True).iterator()
        ):
            for name in p_names:
                if not name:
                    continue
                for chunk in name.split(" "):
                    options["outfile"].write(chunk.strip() + "\n")
