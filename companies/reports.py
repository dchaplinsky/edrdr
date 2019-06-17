import random

from django.db.models import Count, Q
from tqdm import tqdm
from .models import *
from xlsxwriter import Workbook

random.seed(1337)


class GlobalStats:
    @staticmethod
    def write_bo_to_excel(fp, ids):
        outfile = Workbook(fp, {"remove_timezone": True})

        worksheet = outfile.add_worksheet()
        curr_line = 0
        worksheet.write(curr_line, 0, "ЄДРПОУ")
        worksheet.write(curr_line, 1, "З")
        worksheet.write(curr_line, 2, "По")
        worksheet.write(curr_line, 3, "Власник (ПІБ)")
        worksheet.write(curr_line, 4, "Власник (Повний запис)")
        dt_format = outfile.add_format({"num_format": "dd/mm/yy"})
        header_format = outfile.add_format({'bold': True, 'align': 'center_across'})


        if isinstance(ids, list):
            ids = {"": ids}

        for section, values in ids.items():
            if section:
                worksheet.merge_range(curr_line, 0, curr_line, 4, section, header_format)
                curr_line += 1

            for company_edrpou in enumerate(values):
                try:
                    curr_line += 1
                    if isinstance(company_edrpou, Company):
                        company = company_edrpou
                        company_edrpou = company.pk
                    else:
                        company_edrpou = company_edrpou.strip().lstrip("0")
                        company = Company.objects.get(pk=company_edrpou)

                    worksheet.write(curr_line, 0, company_edrpou)

                    grouped_records = company.get_grouped_record(
                        persons_filter_clause=models.Q(person_type="owner")
                    )["grouped_persons_records"]

                    if not grouped_records:
                        worksheet.write(curr_line, 1, "Бенефіціарів не вказано")
                    else:
                        for group in grouped_records:
                            worksheet.write(
                                curr_line, 1, group["start_revision"].created, dt_format
                            )
                            worksheet.write(
                                curr_line, 2, group["finish_revision"].created, dt_format
                            )

                            for r in group["record"]:
                                worksheet.write(curr_line, 3, ", ".join(r.name))
                                worksheet.write(curr_line, 4, r.raw_record)
                                curr_line += 1

                        curr_line -= 1

                except Company.DoesNotExist:
                    worksheet.write(curr_line, 0, company_edrpou)
                    worksheet.write(curr_line, 1, "Компанію не знайдено")

            outfile.close()

    def latest_revision(self):
        return Revision.objects.order_by("-created").first()

    def pick_sample(self, ids, number_of_samples=1000):
        return Company.objects.filter(
            pk__in=random.choices(list(ids), k=min(number_of_samples, len(ids)))
        )

    def count_and_sample(self, ids, number_of_samples=1000):
        return len(ids), self.pick_sample(ids, number_of_samples)

    def _filter_snapshots(self, extra=Q()):
        return set(
            CompanySnapshotFlags.objects.filter(revision=self.latest_revision())
            .filter(extra)
            .values_list("company_id", flat=True)
            .distinct()
        )

    def all_company_ids(self):
        return self._filter_snapshots()

    def all_companies_with_bo(self):
        return self._filter_snapshots(Q(has_bo=True))

    def all_companies_with_bo_persons(self):
        return self._filter_snapshots(Q(has_bo_persons=True))

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
            CompanySnapshotFlags.objects.filter(
                revision=self.latest_revision(), has_bo_companies=True
            )
            .values_list("company_id", flat=True)
            .distinct()
        )

    def all_companies_with_only_persons_founder_and_no_bo(self):
        return self._filter_snapshots(
            Q(has_only_persons_founder=True)
            & Q(has_bo_persons=False)
            & Q(has_dereferenced_bo=False)
        )

    def all_companies_with_only_company_founder_and_no_bo(self):
        return self._filter_snapshots(
            Q(has_only_companies_founder=True) & Q(has_bo=False)
        )

    def all_companies_with_company_founder_and_no_bo(self):
        return self._filter_snapshots(Q(has_founder_companies=True) & Q(has_bo=False))

    def all_companies_with_only_persons_founder_and_different_bo(self):
        return self._filter_snapshots(
            Q(has_only_persons_founder=True)
            & Q(has_bo_persons=True)
            & Q(has_same_person_as_bo_and_founder=False)
        )

    def all_companies_with_only_persons_founder_and_totally_different_bo(self):
        return self._filter_snapshots(
            Q(has_only_persons_founder=True)
            & Q(has_bo_persons=True)
            & Q(has_same_person_as_bo_and_founder=False)
            & Q(has_very_similar_person_as_bo_and_founder=False)
        )

    def all_companies_with_only_persons_bo_and_same_head(self):
        return self._filter_snapshots(
            Q(has_bo_persons=True)
            & Q(has_same_person_as_bo_and_head=True)
        )

    def all_companies_with_only_persons_bo_and_same_head_fuzzy(self):
        return self._filter_snapshots(
            Q(has_bo_persons=True)
            & (Q(has_same_person_as_bo_and_head=True) | Q(has_very_similar_person_as_bo_and_head=True))
        )

    def all_companies_with_bo_in_crimea(self):
        return self._filter_snapshots(
            Q(has_bo_in_crimea=True)
        )

    def all_companies_with_bo_on_occupied_soil(self):
        return self._filter_snapshots(
            Q(has_bo_on_occupied_soil=True)
        )

    def all_companies_that_has_changes_in_bo(self):
        return self._filter_snapshots(
            Q(has_changes_in_bo=True)
        )

    def all_companies_that_is_acting_and_explicitly_stated_that_has_no_bo(self):
        return self._filter_snapshots(
            Q(acting_and_explicitly_stated_that_has_no_bo=True)
        )

    def all_companies_with_foreign_bo(self):
        return self._filter_snapshots(
            ~Q(all_bo_countries__len=0) & ~Q(all_bo_countries=["україна"])
        )

    def all_companies_with_same_bo(self):
        return set(
            Person.objects.filter(
                person_type="owner", 
                revisions__contains=[self.latest_revision()]
            ).values("name").annotate(cnt=Count("name")).filter(cnt__gte=10).values_list()
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


    def number_of_companies_with_only_persons_founder_and_no_bo(self):
        """
        Скільки компаній, де власник є фізична особа, не вказано кінцевого вигодоодержувача
        """

        return self.count_and_sample(
            self.all_companies_with_only_persons_founder_and_no_bo()
        )

    def number_of_companies_with_only_company_founder_and_no_bo(self):
        """
        Скільки компаній, де власником є тільки юридичні особи, не вказано кінцевого вигоодержувача
        """

        return self.count_and_sample(
            self.all_companies_with_only_company_founder_and_no_bo()
        )

    def number_of_companies_with_company_founder_and_no_bo(self):
        """
        Скільки компаній, де власником є хоча б одна юридична особа, не вказано кінцевого вигоодержувача
        """

        return self.count_and_sample(
            self.all_companies_with_company_founder_and_no_bo()
        )

    def number_of_companies_with_only_persons_founder_and_different_bo(self):
        """
        У скількох компаніях, де власниками є тільки фізичні особи, та є кінцеві вигодоодержувачі-фізособи, кінцеві вигодоодержувачі відрізняються від власників
        """

        return self.count_and_sample(
            self.all_companies_with_only_persons_founder_and_different_bo()
        )

    def number_of_companies_with_only_persons_founder_and_totally_different_bo(self):
        """
        У скількох компаніях, де власниками є тільки фізичні особи, та є кінцеві вигодоодержувачі-фізособи, кінцеві вигодоодержувачі відрізняються від власників (враховуючи неточності у написанні ПІБ)
        """

        return self.count_and_sample(
            self.all_companies_with_only_persons_founder_and_totally_different_bo()
        )

    def number_of_companies_with_only_persons_bo_and_same_head(self):
        """
        У скількох компаніях де кінцевим вигодоодержувачем є тільки фізособи директор вказаний як кінцевий вигодоодержувач
        """

        return self.count_and_sample(
            self.all_companies_with_only_persons_bo_and_same_head()
        )

    def number_of_companies_with_only_persons_bo_and_same_head_fuzzy(self):
        """
        У скількох компаніях де кінцевим вигодоодержувачем є тільки фізособи директор вказаний як кінцевий вигодоодержувач (враховуючи неточності у написанні ПІБ)
        """

        return self.count_and_sample(
            self.all_companies_with_only_persons_bo_and_same_head_fuzzy()
        )


    def number_of_companies_with_bo_in_crimea(self):
        """
        У скількох компаніях бенефіціарним власником вказано громадян України, прописка яких на окупованих територіях (Крим)
        """

        return self.count_and_sample(self.all_companies_with_bo_in_crimea())


    def number_of_companies_with_bo_on_occupied_soil(self):
        """
        У скількох компаніях бенефіціарним власником вказано громадян України, прописка яких на окупованих територіях (ОРДЛО)
        """

        return self.count_and_sample(self.all_companies_with_bo_on_occupied_soil())


    def number_of_companies_that_has_changes_in_bo(self):
        """
        Кількість компаній, де змінювався бенефіціарний власник
        """

        return self.count_and_sample(self.all_companies_that_has_changes_in_bo())


    def number_of_companies_that_is_acting_and_explicitly_stated_that_has_no_bo(self):
        """
        Скільки компаній подало що бенефіціарний власник “відсутній”
        """

        return self.count_and_sample(
            self.all_companies_that_is_acting_and_explicitly_stated_that_has_no_bo()
        )


    def number_of_companies_with_foreign_bo(self):
        """
        У скількох компаніях бенефіціарним власником вказано іноземців
        """

        return self.count_and_sample(
            self.all_companies_with_foreign_bo()
        )

