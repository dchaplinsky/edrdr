import sys
import argparse
from django.core.management.base import BaseCommand
from django.conf import settings
from companies.reports import GlobalStats
from tqdm import tqdm


class Command(BaseCommand):
    FIELDS_TO_CALCULATE = [
        "number_of_companies",
        "number_of_companies_with_bo",
        "number_of_companies_with_bo_person",
        "number_of_companies_with_bo_company",
        "number_of_companies_with_only_persons_founder_and_no_bo",
        "number_of_companies_with_only_company_founder_and_no_bo",
        "number_of_companies_with_company_founder_and_no_bo",
        "number_of_companies_with_only_persons_founder_and_different_bo",
        "number_of_companies_with_only_persons_founder_and_totally_different_bo",
        "number_of_companies_with_only_persons_bo_and_same_head",
        "number_of_companies_with_only_persons_bo_and_same_head_fuzzy",
        "number_of_companies_with_bo_in_crimea",
        "number_of_companies_with_bo_on_occupied_soil",
        "number_of_companies_that_has_changes_in_bo",
        "number_of_companies_that_is_acting_and_explicitly_stated_that_has_no_bo",
        "number_of_companies_with_foreign_bo",
    ]

    def render_sample(self, sample):
        return "\n" + "\n".join(
            map(
                lambda x: "{}/edr{}".format(settings.SITE_URL, x.get_absolute_url()),
                sample,
            )
        )

    def handle(self, *args, **options):
        gs = GlobalStats()

        for k in tqdm(self.FIELDS_TO_CALCULATE):
            method = getattr(gs, k)

            description = method.__doc__ or k
            count, sample = method()
            print(
                "{} ({}): {}, наприклад такі: {}".format(
                    description.strip(), k, count, self.render_sample(sample[:10])
                )
            )

            with open("{}_sample.xlsx".format(k), "wb") as fp:
                gs.write_bo_to_excel(fp, sample)
