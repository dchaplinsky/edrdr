from django.core.management.base import BaseCommand
from django.db import models

from tqdm import tqdm
from companies.models import Company


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action='store_true',
            default=False,
            help='Force recalculation of all flags',
        )

        parser.add_argument(
            "--revision_id",
            default=None
        )

        parser.add_argument(
            "--limit",
            type=int
        )


    def handle(self, *args, **options):
        qs = Company.objects.all()

        for i, company in tqdm(enumerate(qs.iterator()), total=qs.count()):
            company.take_snapshot_of_flags(options["revision_id"], options["force"])
            
            if options["limit"] is not None and i + 1 > options["limit"]:
                break