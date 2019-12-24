from tqdm import tqdm
from django.core.management.base import BaseCommand

from companies.models import CompanyRecord, Person, Revision
from collections import Counter


class Command(BaseCommand):
    def handle(self, *args, **options):
        company_revs = Counter()
        person_revs = Counter()

        for rec in tqdm(
            CompanyRecord.objects.only("revisions").nocache().iterator(),
            total=CompanyRecord.objects.count(),
        ):
            company_revs.update(set(rec.revisions))

        for r in Revision.objects.filter(imported=True, ignore=False).iterator():
            if company_revs.get(r.pk, 0) < 1000000:
                print(
                    "{}, created on {} has only {} company records".format(
                        r.pk, r.created, company_revs.get(r.pk, 0)
                    )
                )


        for rec in tqdm(
            Person.objects.only("revisions").nocache().iterator(),
            total=Person.objects.count(),
        ):
            person_revs.update(set(rec.revisions))

        for r in Revision.objects.filter(imported=True, ignore=False).iterator():
            if person_revs.get(r.pk, 0) < 1000000:
                print(
                    "{}, created on {} has only {} person records".format(
                        r.pk, r.created, person_revs.get(r.pk, 0)
                    )
                )
