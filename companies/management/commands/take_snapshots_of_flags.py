from django.core.management.base import BaseCommand
from django.db import models

from tqdm import tqdm
from companies.models import Company, CompanyRecord


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

        mass_registration = CompanyRecord.objects.mass_registration_addresses(options["revision_id"])
        total = qs.count()
        if options["limit"] is not None:
            total = min(total, options["limit"])

        for i, company in tqdm(enumerate(qs.iterator()), total=total):
            company.take_snapshot_of_flags(options["revision_id"], options["force"], mass_registration)
            
            if options["limit"] is not None and i + 1 > options["limit"]:
                break