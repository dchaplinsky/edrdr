import sys
import argparse
from django.db.models import Q
from django.core.management.base import BaseCommand
from django.conf import settings
from csv import DictReader
from tqdm import tqdm

from companies.models import OwnedByCompany, Company, CompanySnapshotFlags


class Command(BaseCommand):
    def handle(self, *args, **options):
        qs = OwnedByCompany.objects.all()
        CompanySnapshotFlags.objects.update(has_founder_companies=False, has_only_companies_founder=False)

        for owner in tqdm(qs.values_list("company", flat=True).nocache().iterator(), total=qs.count()):
            CompanySnapshotFlags.objects.filter(company_id=owner).update(
                has_founder_companies=True,
                has_only_persons_founder=False,
                has_only_companies_founder=Q(has_founder_persons=False)
            )
