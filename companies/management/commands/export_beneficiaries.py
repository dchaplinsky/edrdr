import sys
import argparse
from django.core.management.base import BaseCommand
from django.db import models

from tqdm import tqdm
from xlsxwriter import Workbook
from companies.models import Company


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "infile", nargs="?", type=argparse.FileType("r"), default=sys.stdin
        )
        parser.add_argument("outfile", type=argparse.FileType("wb"))

    def handle(self, *args, **options):
        outfile = Workbook(options["outfile"], {"remove_timezone": True})

        worksheet = outfile.add_worksheet()
        curr_line = 0
        worksheet.write(curr_line, 0, "ЄДРПОУ")
        worksheet.write(curr_line, 1, "З")
        worksheet.write(curr_line, 2, "По")
        worksheet.write(curr_line, 3, "Власник (ПІБ)")
        worksheet.write(curr_line, 4, "Власник (Повний запис)")
        dt_format = outfile.add_format({"num_format": "dd/mm/yy"})

        for i, company_edrpou in tqdm(enumerate(options["infile"])):
            company_edrpou = company_edrpou.strip().lstrip("0")

            try:
                curr_line += 1
                company = Company.objects.get(pk=company_edrpou)

                worksheet.write(curr_line, 0, company_edrpou)

                grouped_records = company.get_grouped_record(
                    persons_filter_clause=models.Q(person_type="owner")
                )["grouped_persons_records"]

                if not grouped_records:
                    worksheet.write(
                        curr_line, 1, "Бенефіціарів не вказано"
                    )
                else:
                    for group in grouped_records:
                        worksheet.write(
                            curr_line, 1, group["start_revision"].created, dt_format
                        )
                        worksheet.write(
                            curr_line, 2, group["finish_revision"].created, dt_format
                        )

                        for r in group["record"]:
                            worksheet.write(
                                curr_line, 3, ", ".join(r.name)
                            )
                            worksheet.write(
                                curr_line, 4, r.raw_record
                            )
                            curr_line += 1

                    curr_line -= 1

            except Company.DoesNotExist:
                worksheet.write(curr_line, 0, company_edrpou)
                worksheet.write(curr_line, 1, "Компанію не знайдено")

            if i > 1000:
                break

        outfile.close()
