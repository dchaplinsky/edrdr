import random

from django.db.models import Count, Q
from .models import *

random.seed(1337)


class GlobalStats:
    def latest_revision(self):
        return Revision.objects.order_by("-created").first()

    def all_company_ids(self):
        return set(
            CompanyRecord.objects.filter(
                revisions__contains=[self.latest_revision().pk]
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def pick_sample(self, ids, number_of_samples=10):
        return Company.objects.filter(
            pk__in=random.choices(list(ids), k=number_of_samples)
        )

    def count_and_sample(self, ids, number_of_samples=10):
        return len(ids), self.pick_sample(ids, number_of_samples)

    def all_companies_with_bo(self):
        return set(
            Person.objects.filter(
                person_type="owner", revisions__contains=[self.latest_revision().pk]
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def all_companies_with_bo_persons(self):
        return set(
            Person.objects.filter(
                person_type="owner",
                revisions__contains=[self.latest_revision().pk],
                name__len__gt=0,
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def all_companies_with_founder_persons(self):
        return set(
            Person.objects.filter(
                person_type="founder",
                revisions__contains=[self.latest_revision().pk],
                name__len__gt=0,
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def all_companies_with_founder_company(self):
        return set(
            Person.objects.filter(
                person_type="founder",
                revisions__contains=[self.latest_revision().pk],
                name__len=0,
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def all_companies_with_bo_companies(self):
        return set(
            Person.objects.filter(
                person_type="owner",
                revisions__contains=[self.latest_revision().pk],
                name__len=0,
                was_dereferenced=False,
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def all_companies_with_founder_only_persons(self):
        return (
            self.all_companies_with_founder_persons()
            - self.all_companies_with_founder_company()
        )

    def all_companies_with_founder_only_companies(self):
        return (
            self.all_companies_with_founder_company()
            - self.all_companies_with_founder_persons()
        )

    def all_companies_with_dereferenced(self):
        return set(
            Person.objects.filter(
                person_type="owner",
                revisions__contains=[self.latest_revision().pk],
                was_dereferenced=True,
            )
            .values_list("company", flat=True)
            .distinct()
        )

    def number_of_companies(self):
        """
        Скільки в реєстрі компаній
        """

        ids = self.all_company_ids()
        return self.count_and_sample(ids)

    def number_of_companies_with_bo(self):
        """
        Скільки в реєстрі компаній із зазначеним бенефіціаром
        """
        ids = self.all_companies_with_bo()
        return self.count_and_sample(ids)

    def number_of_companies_with_bo_person(self):
        """
        Скільки в реєстрі компаній де хоча б одним з бенефіціарів зазначена персона
        """
        ids = self.all_companies_with_bo_persons()
        return self.count_and_sample(ids)

    def number_of_companies_with_bo_company(self):
        """
        Скільки в реєстрі компаній де бенефіціаром зазначена тільки юр. особа/особи
        """
        ids = self.all_companies_with_bo_companies()
        return self.count_and_sample(ids)

    def compare_founder_persons_and_bo_persons(self, edrpou):
        bos = Person.objects.filter(
            company=edrpou,
            person_type="owner",
            name__len__gt=0,
            revisions__contains=[self.latest_revision().pk],
        ).values_list("name", flat=True)

        all_bos = set()
        for b in bos:
            all_bos |= set(b)

        founders = Person.objects.filter(
            company=edrpou,
            person_type="founder",
            name__len__gt=0,
            revisions__contains=[self.latest_revision().pk],
        ).values_list("name", flat=True)
        all_founders = set()
        for f in founders:
            all_founders |= set(f)

        intersection = all_bos & all_founders
        if not intersection:
            print(all_bos, all_founders)
        return all_bos & all_founders

    def number_of_companies_with_only_persons_founder_and_no_bo(self):
        """
        Скільки компаній, де власник є фізична особа, не вказано кінцевого вигодоодержувача
        """
        founder_only_person = self.all_companies_with_founder_only_persons()
        bo_person = self.all_companies_with_bo_persons()
        bo_dereferenced = self.all_companies_with_dereferenced()

        founder_only_person_no_bo = founder_only_person - bo_person - bo_dereferenced

        return self.count_and_sample(founder_only_person_no_bo)

    def number_of_companies_with_only_company_founder_and_no_bo(self):
        """
        Скільки компаній, де власником є тільки юридичні особи, не вказано кінцевого вигоодержувача
        """
        founder_only_company = self.all_companies_with_founder_only_companies()
        bo = self.all_companies_with_bo()

        founder_only_company_no_bo = founder_only_company - bo

        return self.count_and_sample(founder_only_company_no_bo)

    def number_of_companies_with_company_founder_and_no_bo(self):
        """
        Скільки компаній, де власником є хоча б одна юридична особа, не вказано кінцевого вигоодержувача
        """
        founder_company = self.all_companies_with_founder_company()

        bo = self.all_companies_with_bo()

        founder_only_company_no_bo = founder_company - bo

        return self.count_and_sample(founder_only_company_no_bo)

    def number_of_companies_with_only_persons_founder_and_different_bo(self):
        """
        У скількох компаніях, де власниками є тільки фізичні особи, та є кінцеві вигодоодержувачі-фізособи, кінцеві вигодоодержувачі відрізняються від власників
        """
        founder_only_person = self.all_companies_with_founder_only_persons()

        persons_bo = self.all_companies_with_bo_persons()

        founder_only_person_with_bo_persons = founder_only_person & persons_bo

        for i, pk in enumerate(founder_only_person_with_bo_persons):
            compare_them = self.compare_founder_persons_and_bo_persons(pk)
            if not compare_them:
                print(pk, compare_them)
            if i > 1000:
                break

        return self.count_and_sample(founder_only_person_with_bo_persons)
