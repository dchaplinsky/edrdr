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
        "breakdown_of_companies_with_foreign_bo",
        "number_of_companies_with_changes_in_founders_but_not_bo",
        "number_of_companies_with_changes_in_bo_but_not_founders",
        "number_of_companies_with_british_founders",
        "number_of_companies_with_british_bo",
        "breakdown_by_mass_bo",
        "breakdown_by_mass_bo_on_cyprus",
        "breakdown_by_number_of_bo",
        "breakdown_by_mass_registration_addresses",
    ]

    def render_sample(self, sample):
        return "\n\t" + "\n\t".join(
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

            if isinstance(sample, dict):
                print(
                    "{} ({}): {}, детальна розбивка:".format(
                        description.strip(), k, count
                    )
                )

                for bucket_name, sub_sample in list(sample.items())[:10]:
                    print(
                        "{}, наприклад такі: {}".format(
                            bucket_name,
                            self.render_sample(sub_sample[:10]),
                        )
                    )
            else:
                print(
                    "{} ({}): {}, наприклад такі: {}".format(
                        description.strip(), k, count, self.render_sample(sample[:10])
                    )
                )

            with open("{}_sample.xlsx".format(k), "wb") as fp:
                gs.write_bo_to_excel(fp, sample)
