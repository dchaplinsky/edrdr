import re
import sys
import json
import argparse
from functools import reduce
from itertools import permutations, product, islice, zip_longest
from operator import mul
from Levenshtein import jaro

from django.core.management.base import BaseCommand
from tqdm import tqdm
from companies.models import Company, Revision


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(sorted(obj))
        return json.JSONEncoder.default(self, obj)


class Command(BaseCommand):
    def dump_json(self, rec):
        return json.dumps(rec, ensure_ascii=False, sort_keys=True, cls=SetEncoder, indent=4)

    @staticmethod
    def compare_two_names(
        name1, name2, max_splits=7, straight_limit=0.93, smart_limit=0.95
    ):
        def normalize_name(s):
            return re.sub(r"\s+", " ", s.strip().replace("-", " "))

        def slugify_name(s):
            return (
                s.replace(" ", "")
                .replace(".", "")
                .replace('"', "")
                .replace("'", "")
                .replace("’", "")
            )

        name1 = normalize_name(name1)
        name2 = normalize_name(name2)

        if slugify_name(name1) == slugify_name(name2):
            return True

        splits = name2.split(" ")

        straight_similarity = jaro(name1, name2)
        if straight_similarity > smart_limit:
            return True

        if straight_similarity > 0.8:
            min_pair_distance = 1
            for a, b in zip_longest(name1.split(" "), splits):
                if a is not None and b is not None:
                    min_pair_distance = min(jaro(a, b), min_pair_distance)

            if min_pair_distance > 0.9:
                if len(splits) > 1:
                    tqdm.write("Hmmm, looks like a match {} {}".format(name1, name2))
                return True
            else:
                tqdm.write("Check if it's match: {} {}".format(name1, name2))

        limit = reduce(mul, range(1, max_splits + 1))

        if len(splits) > max_splits:
            tqdm.write("Too much permutations for {}".format(name2))

        max_similarity = max(
            jaro(name1, " ".join(opt)) for opt in islice(permutations(splits), limit)
        )

        return max_similarity > smart_limit

    def add_arguments(self, parser):
        parser.add_argument(
            "outfile", nargs="?", type=argparse.FileType("w"), default=sys.stdout
        )

        parser.add_argument("--limit", type=int)

    def handle(self, *args, **options):
        latest_rev = Revision.objects.order_by("-created").first()
        qs = Company.objects.all()  # .filter(edrpou__in=["41112805", "39032637"])
        for i, company in tqdm(enumerate(qs.nocache().iterator()), total=qs.count()):
            company_rec = {
                "edrpou": company.edrpou,
                "founder": [],
                "owner": [],
                "head": [],
                "connections": [],
            }

            for person in company.persons.only("revisions", "name", "person_type"):
                for name in person.name:
                    company_rec[person.person_type].append(
                        {"name": name, "is_current": latest_rev.pk in person.revisions}
                    )

            for k in ["founder", "owner", "head"]:
                for p in company_rec[k]:
                    merged = False

                    for c in company_rec["connections"]:
                        for name in c["names"]:
                            comparison_result = self.compare_two_names(p["name"], name)
                            if not comparison_result:
                                comparison_result = self.compare_two_names(
                                    name, p["name"]
                                )

                            if comparison_result:
                                c["names"] |= set([p["name"].lower()])
                                # if len(c["names"]) > 1:
                                #     print(c["names"])
                                c[f"is_{k}"] = True
                                if f"is_current_{k}" in c:
                                    c[f"is_current_{k}"] |= p["is_current"]
                                else:
                                    c[f"is_current_{k}"] = p["is_current"]

                                if merged:
                                    tqdm.write(
                                        "Hmm, something fishy: {} {}".format(
                                            p["name"], name
                                        )
                                    )

                                merged = True
                                break
                            else:
                                if self.compare_two_names(
                                    p["name"].replace(" ", ""), name.replace(" ", "")
                                ):
                                    tqdm.write(
                                        "Silly match {}, {}".format(p["name"], name)
                                    )

                    if not merged:
                        company_rec["connections"].append(
                            {
                                "names": set([p["name"].lower()]),
                                f"is_{k}": True,
                                f"is_current_{k}": p["is_current"],
                            }
                        )

            options["outfile"].write(self.dump_json(company_rec) + "\n")

            if options["limit"] and i > options["limit"]:
                break
