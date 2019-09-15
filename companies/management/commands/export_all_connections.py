import re
import sys
import json
import argparse

from tools.names import compare_two_names, full_compare

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
                            if full_compare(p["name"], name):
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
                                if compare_two_names(
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
