import random

from django.db.models import Count, Q
from django.conf import settings
from tqdm import tqdm
from .models import *
from xlsxwriter import Workbook
from collections import OrderedDict
from datetime import date

random.seed(1337)


class GlobalStats:
    @staticmethod
    def write_bo_to_excel(fp, ids):
        outfile = Workbook(fp, {"remove_timezone": True})

        worksheet = outfile.add_worksheet()
        curr_line = 0
        worksheet.write(curr_line, 0, "ЄДРПОУ")
        worksheet.write(curr_line, 1, "Назва")
        worksheet.write(curr_line, 2, "ОПФ")
        worksheet.write(curr_line, 3, "Власники")
        worksheet.write(curr_line, 4, "З")
        worksheet.write(curr_line, 5, "По")
        worksheet.write(curr_line, 6, "Власник (ПІБ)")
        worksheet.write(curr_line, 7, "Власник (Повний запис)")
        worksheet.write(curr_line, 8, "Статутний капітал")
        worksheet.write(curr_line, 10, "Поточний статус")
        dt_format = outfile.add_format({"num_format": "dd/mm/yy"})
        header_format = outfile.add_format({"bold": True, "align": "center_across"})
        owner_format = outfile.add_format({"color": "green"})
        founder_format = outfile.add_format({"color": "blue"})
        rev = GlobalStats.latest_revision()
        curr_line += 1

        if not isinstance(ids, dict):
            ids = {"": ids}

        with tqdm(total=sum(map(len, ids.values()))) as pbar:
            for section, values in ids.items():
                if section:
                    worksheet.merge_range(
                        curr_line, 0, curr_line, 8, section, header_format
                    )
                    curr_line += 1

                for company_edrpou in values:
                    pbar.update(1)
                    try:
                        curr_line += 1
                        if isinstance(company_edrpou, Company):
                            company = company_edrpou
                            company_edrpou = company.pk
                        else:
                            company_edrpou = int(company_edrpou.strip().lstrip("0"))
                            company = Company.objects.get(pk=company_edrpou)

                        latest_company_rec = CompanyRecord.objects.filter(
                            company_id=int(company_edrpou), revisions__contains=[rev.pk]
                        ).first()

                        latest_founder_recs = Person.objects.filter(
                            company_id=int(company_edrpou),
                            revisions__contains=[rev.pk],
                            person_type="founder",
                        ).values_list("name", flat=True)

                        latest_flags_rec = CompanySnapshotFlags.objects.filter(
                            company_id=int(company_edrpou), revision_id=rev.pk
                        ).first()

                        worksheet.write_url(
                            curr_line,
                            0,
                            "{}/edr/uk/company/{}".format(
                                settings.SITE_URL, company_edrpou
                            ),
                            string=str(company_edrpou).rjust(8, "0"),
                        )

                        grouped_records = company.get_grouped_record(
                            persons_filter_clause=models.Q(
                                person_type__in=["owner", "founder"]
                            )
                        )["grouped_persons_records"]

                        if latest_company_rec is not None:
                            worksheet.write(
                                curr_line,
                                1,
                                latest_company_rec.short_name
                                or latest_company_rec.name,
                            )

                            worksheet.write(
                                curr_line, 2, latest_company_rec.form
                            )

                            worksheet.write(
                                curr_line, 9, latest_company_rec.get_status_display()
                            )

                        if latest_flags_rec is not None:
                            worksheet.write(
                                curr_line, 8, latest_flags_rec.charter_capital
                            )

                        if latest_founder_recs:
                            worksheet.write(
                                curr_line,
                                3,
                                ", ".join(
                                    set(
                                        name
                                        for rec in latest_founder_recs
                                        for name in rec
                                    )
                                ),
                            )

                        if not grouped_records:
                            worksheet.write(
                                curr_line, 4, "Бенефіціарів/власників не вказано"
                            )
                        else:
                            for group in grouped_records:
                                worksheet.write(
                                    curr_line,
                                    4,
                                    group["start_revision"].created,
                                    dt_format,
                                )
                                worksheet.write(
                                    curr_line,
                                    5,
                                    group["finish_revision"].created,
                                    dt_format,
                                )

                                for r in group["record"]:
                                    worksheet.write(curr_line, 6, ", ".join(r.name))
                                    worksheet.write(
                                        curr_line,
                                        7,
                                        r.raw_record,
                                        owner_format
                                        if r.person_type == "owner"
                                        else founder_format,
                                    )
                                    curr_line += 1

                            curr_line -= 1

                    except Company.DoesNotExist:
                        worksheet.write(curr_line, 0, company_edrpou)
                        worksheet.write(curr_line, 1, "Компанію не знайдено")

        outfile.close()

    @staticmethod
    def latest_revision():
        return Revision.objects.order_by("-created").first()

    def pick_sample(self, ids, number_of_samples=1000):
        sample = list(ids)
        random.shuffle(sample)

        return Company.objects.filter(
            pk__in=sample[: min(number_of_samples, len(sample))]
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

    def all_companies_with_only_company_founder_and_no_bo_after_dday(self):
        return self._filter_snapshots(
            Q(has_only_companies_founder=True)
            & Q(has_bo=False)
            & Q(reg_date__gte=date(2015, 9, 25))
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
            Q(has_bo_persons=True) & Q(has_same_person_as_bo_and_head=True)
        )

    def all_companies_with_only_persons_bo_and_same_head_fuzzy(self):
        return self._filter_snapshots(
            Q(has_bo_persons=True)
            & (
                Q(has_same_person_as_bo_and_head=True)
                | Q(has_very_similar_person_as_bo_and_head=True)
            )
        )

    def all_companies_with_bo_in_crimea(self):
        return self._filter_snapshots(Q(has_bo_in_crimea=True))

    def all_companies_with_bo_on_occupied_soil(self):
        return self._filter_snapshots(Q(has_bo_on_occupied_soil=True))

    def all_companies_that_has_changes_in_bo(self):
        return self._filter_snapshots(Q(has_changes_in_bo=True))

    def all_companies_that_is_acting_and_explicitly_stated_that_has_no_bo(self):
        return self._filter_snapshots(
            Q(acting_and_explicitly_stated_that_has_no_bo=True)
        )

    def all_companies_with_foreign_bo(self):
        return self._filter_snapshots(
            ~Q(all_bo_countries__len=0) & ~Q(all_bo_countries=["україна"])
        )

    def all_companies_with_bo_of_particular_country(self, country):
        return self._filter_snapshots(Q(all_bo_countries=country))

    def all_companies_with_particular_bo(self, name):
        return self._filter_snapshots(Q(all_owner_persons__contains=[name]))

    def all_companies_with_same_bo(self):
        return set(
            Person.objects.filter(
                person_type="owner", revisions__contains=[self.latest_revision()]
            )
            .values("name")
            .annotate(cnt=Count("name"))
            .filter(cnt__gte=10)
            .values_list()
        )

    def all_companies_with_changes_in_founders_but_not_bo(self):
        return self._filter_snapshots(
            Q(has_changes_in_bo=False, has_changes_in_ownership=True)
        )

    def all_companies_with_changes_in_bo_but_not_founders(self):
        return self._filter_snapshots(
            Q(has_changes_in_bo=True, has_changes_in_ownership=False)
        )

    def all_companies_with_british_founders(self):
        return set(
            Person.objects.filter(
                person_type="founder", revisions__contains=[self.latest_revision().pk]
            )
            .filter(
                Q(raw_record__icontains="СПОЛУЧЕНЕ КОРОЛІВСТВО")
                | Q(raw_record__icontains="британія")
                | Q(raw_record__icontains="англія")
            )
            .values_list("company_id", flat=True)
        ) | self._filter_snapshots(
            Q(all_founder_countries__contains=["британія"])
            | Q(all_founder_countries__contains=["велика британія"])
            | Q(all_founder_countries__contains=["англія"])
        )

    def all_companies_with_british_bo(self):
        return set(
            Person.objects.filter(
                person_type="owner", revisions__contains=[self.latest_revision().pk]
            )
            .filter(
                Q(raw_record__icontains="СПОЛУЧЕНЕ КОРОЛІВСТВО")
                | Q(raw_record__icontains="британія")
                | Q(raw_record__icontains="англія")
            )
            .values_list("company_id", flat=True)
        ) | self._filter_snapshots(
            Q(all_bo_countries__contains=["британія"])
            | Q(all_bo_countries__contains=["велика британія"])
            | Q(all_bo_countries__contains=["англія"])
        )

    def all_companies_with_number_of_bos(self, number):
        return self._filter_snapshots(Q(all_owner_persons__len=number))

    def all_companies_with_ids(self, ids):
        return self._filter_snapshots(Q(company_id__in=ids))

    def all_companies_with_pep_owner(self):
        return self._filter_snapshots(Q(has_pep_owner=True))

    def all_companies_with_pep_owner_in_the_past(self):
        return self._filter_snapshots(Q(had_pep_owner_in_the_past=True))

    def all_companies_with_undeclared_pep_owner(self):
        return self._filter_snapshots(Q(has_undeclared_pep_owner=True))

    def all_companies_with_pep_owner_in_declaration_but_not_registry(self):
        return self._filter_snapshots(
            Q(has_discrepancy_with_declarations=True, has_bo=True)
        )

    def all_companies_with_pep_owner_in_declaration_but_no_bo_in_registry(self):
        return self._filter_snapshots(
            Q(has_discrepancy_with_declarations=True, has_bo=False)
        )

    def all_companies_that_self_owned(self):
        return self._filter_snapshots(Q(self_owned=True))

    def all_companies_that_indirectly_self_owned(self):
        return self._filter_snapshots(Q(indirectly_self_owned=True))

    def all_companies_with_high_risk(self):
        return self._filter_snapshots(
            Q(
                Q(has_same_person_as_head_and_founder=True)
                | Q(has_very_similar_person_as_head_and_founder=True),
                all_founder_persons__len=1,
                has_founder_companies=False,
                has_mass_registration_address=True,
                charter_capital__lte=1000,
                charter_capital__gt=0,
                charter_capital__isnull=False,
            )
        )

    def all_companies_with_high_risk_and_bo(self):
        return self._filter_snapshots(
            Q(
                Q(has_same_person_as_head_and_founder=True)
                | Q(has_very_similar_person_as_head_and_founder=True),
                has_mass_registration_address=True,
                all_founder_persons__len=1,
                has_founder_companies=False,
                charter_capital__lte=1000,
                has_bo=True,
                charter_capital__gt=0,
                charter_capital__isnull=False,
            )
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
            self.all_companies_with_only_company_founder_and_no_bo(),
            number_of_samples=30000,
        )

    def number_of_companies_with_only_company_founder_and_no_bo_after_dday(self):
        """
        Скільки компаній, де власником є тільки юридичні особи, не вказано кінцевого вигоодержувача, що зареєстровані після 25 вересня 2015
        """

        return self.count_and_sample(
            self.all_companies_with_only_company_founder_and_no_bo_after_dday(),
            number_of_samples=30000,
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

        return self.count_and_sample(self.all_companies_with_foreign_bo())

    def breakdown_of_companies_with_foreign_bo(self):
        """
        Яка розбивка по країнах компаній де бенефіціарним власником вказано іноземців
        """

        res = []
        total_cnt = 0
        for country in (
            CompanySnapshotFlags.objects.exclude(all_bo_countries=[])
            .exclude(all_bo_countries=["україна"])
            .values("all_bo_countries")
            .annotate(cnt=Count("all_bo_countries"))
            .values("all_bo_countries", "cnt")
            .order_by("-cnt")
        ):
            sub_cnt, sub_res = self.count_and_sample(
                self.all_companies_with_bo_of_particular_country(
                    country["all_bo_countries"]
                )
            )

            total_cnt += sub_cnt
            key = "BO Country: {} ({})".format(
                ", ".join(country["all_bo_countries"]), sub_cnt
            )

            res.append((key, sub_res))

        return total_cnt, OrderedDict(res)

    def number_of_companies_with_changes_in_founders_but_not_bo(self):
        """Скільки підприємств змінили бенефіціарного власника без зміни структури власності"""
        return self.count_and_sample(
            self.all_companies_with_changes_in_founders_but_not_bo()
        )

    def number_of_companies_with_changes_in_bo_but_not_founders(self):
        """Скільки компаній змінили структуру власності без зміни бенефіціарного власника"""
        return self.count_and_sample(
            self.all_companies_with_changes_in_bo_but_not_founders()
        )

    def number_of_companies_with_british_founders(self):
        """Кількість компаній, де власниками є британські компанії"""
        return self.count_and_sample(self.all_companies_with_british_founders(), number_of_samples=5000)

    def number_of_companies_with_british_bo(self):
        """Кількість компаній, де бенефіціарами є британські компанії"""
        return self.count_and_sample(self.all_companies_with_british_bo(), number_of_samples=5000)

    def breakdown_by_mass_bo(self):
        """
        Кількість фізичних осіб, яких вказано бенефіціарними власниками понад 10 разів
        """
        res = []
        total_cnt = 0
        rev = self.latest_revision()

        for p in (
            Person.objects.filter(
                person_type="owner", revisions__contains=[rev.pk], name__len__gt=0
            )
            .values("name")
            .annotate(cnt=Count("name"))
            .filter(cnt__gte=10)
            .order_by("-cnt")
            .values("name", "cnt")
        ):
            sub_cnt, sub_res = self.count_and_sample(
                self.all_companies_with_particular_bo(p["name"])
            )

            key = "BO name: {} ({})".format(", ".join(p["name"]), sub_cnt)
            total_cnt += sub_cnt

            res.append((key, sub_res))

        return total_cnt, OrderedDict(res)

    def breakdown_by_mass_bo_on_cyprus(self):
        """
        Кількість фізичних осіб з Кіпру, яких вказано бенефіціарними власниками понад 10 разів
        """
        res = []
        total_cnt = 0
        rev = self.latest_revision()

        for p in (
            Person.objects.filter(
                person_type="owner", revisions__contains=[rev.pk], name__len__gt=0
            )
            .filter(
                Q(country__contains=["кіпр"]) | Q(country__contains=["республіка кіпр"]) | Q(raw_record__icontains="кіпр")
            )
            .values("name")
            .annotate(cnt=Count("name"))
            .filter(cnt__gte=10)
            .order_by("-cnt")
            .values("name", "cnt")
        ):
            sub_cnt, sub_res = self.count_and_sample(
                self.all_companies_with_particular_bo(p["name"])
            )

            key = "BO name: {} ({})".format(", ".join(p["name"]), sub_cnt)
            total_cnt += sub_cnt

            res.append((key, sub_res))

        return total_cnt, OrderedDict(res)

    def breakdown_by_number_of_bo(self):
        """
        Скільки підприємств подали 1 бенефіціарного власника, скільки 2, скільки 3 а скільки 4 і більше?
        """
        res = []
        total_cnt = 0
        rev = self.latest_revision()

        for p in (
            CompanySnapshotFlags.objects.filter(has_bo_persons=True)
            .values("all_owner_persons__len")
            .annotate(count=Count("all_owner_persons__len"))
            .order_by("-all_owner_persons__len")
        ):
            sub_cnt, sub_res = self.count_and_sample(
                self.all_companies_with_number_of_bos(p["all_owner_persons__len"])
            )

            key = "BO count: {} ({})".format(p["all_owner_persons__len"], sub_cnt)
            total_cnt += sub_cnt

            res.append((key, sub_res))

        return total_cnt, OrderedDict(res)

    def breakdown_by_mass_registration_addresses(self):
        """
        ТОП 20 адрес, за якими зареєстровано найбільше компаній
        """
        res = []
        total_cnt = 0
        rev = self.latest_revision()
        mra = list(CompanyRecord.objects.mass_registration_addresses(rev.pk).keys())[
            :800
        ]

        for addr in mra:
            ids = set(
                CompanyRecord.objects.filter(
                    revisions__contains=[rev.pk], shortened_validated_location=addr
                ).values_list("company_id", flat=True)
            )

            sub_cnt, sub_res = self.count_and_sample(self.all_companies_with_ids(ids))

            key = "Mass address {} ({})".format(addr, sub_cnt)
            total_cnt += sub_cnt

            res.append((key, sub_res))

        return total_cnt, OrderedDict(res)

    def number_of_companies_with_pep_owner(self):
        """Кількість компаній, де бенефіціарними власниками є ПЕПи (інформація з декларації за 2018)"""
        return self.count_and_sample(
            self.all_companies_with_pep_owner(), number_of_samples=5000
        )

    def number_of_companies_with_pep_owner_in_the_past(self):
        """Кількість компаній, де бенефіціарними власниками є ПЕПи (інформація з декларацій за 2015-2017)"""
        return self.count_and_sample(
            self.all_companies_with_pep_owner_in_the_past(), number_of_samples=5000
        )

    def number_of_companies_with_undeclared_pep_owner(self):
        """Кількість компаній, де бенефіціарними власниками є ПЕПи (за результатами журналістських рослідувань)"""
        return self.count_and_sample(self.all_companies_with_undeclared_pep_owner())

    def number_of_companies_with_pep_owner_in_declaration_but_not_registry(self):
        """Кількість компаній, де бенефіціарними власниками є ПЕПи (інформація з декларації за 2018), але в реєстрі вказаний інший бенефіціар"""
        return self.count_and_sample(
            self.all_companies_with_pep_owner_in_declaration_but_not_registry()
        )

    def number_of_companies_with_pep_owner_in_declaration_but_no_bo_in_registry(self):
        """Кількість компаній, де бенефіціарними власниками є ПЕПи (інформація з декларації за 2018), але в реєстрі не вказаний бенефіціар"""
        return self.count_and_sample(
            self.all_companies_with_pep_owner_in_declaration_but_no_bo_in_registry()
        )

    def number_of_companies_that_self_owned(self):
        """Кількість компаній, де одним з власників є сама компанія"""
        return self.count_and_sample(self.all_companies_that_self_owned(), number_of_samples=5000)

    def number_of_companies_that_indirectly_self_owned(self):
        """Кількість компаній, де одним з власників є сама компанія через низку інших компаній (до 7)"""
        return self.count_and_sample(self.all_companies_that_indirectly_self_owned(), number_of_samples=5000)

    def number_of_companies_with_high_risk(self):
        """Кількість компаній з ознаками фіктивності: статутний фонд до 1000 грн, директор та власник одна і та ж фізична особа, адреса масової реєстрації."""
        return self.count_and_sample(
            self.all_companies_with_high_risk(), number_of_samples=7000
        )

    def number_of_companies_with_high_risk_and_bo(self):
        """Кількість компаній з ознаками фіктивності та які подали бенефіціара"""
        return self.count_and_sample(
            self.all_companies_with_high_risk_and_bo(), number_of_samples=7000
        )
