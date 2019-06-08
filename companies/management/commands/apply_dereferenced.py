import sys
import redis
import json
import gzip
import argparse
from csv import writer
from hashlib import sha1
from django.core.management.base import BaseCommand
from django.conf import settings
from tqdm import tqdm
from companies.models import Person


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--redis_cache_key",
            default="extractor_dfcf1835c249a2a9efb08e1e66bb4238d4e1f54a",
        )

    def handle(self, *args, **options):
        self.redis = redis.StrictRedis.from_url(settings.PARSING_REDIS)

        rec_buffer = []
        spoiled_buffer = []
        statements = []

        qs = Person.objects.filter(name__len=0, person_type="owner")

        for i, (pk, edrpou, founder_rec) in tqdm(
            enumerate(
                qs.values_list("pk", "company", "raw_record").iterator()
            ),
            total=qs.count(),
        ):
            rec_hash = sha1(founder_rec.lower().encode("utf8")).hexdigest()

            cached = self.redis.hget(options["redis_cache_key"], rec_hash)

            if cached is not None:
                res = json.loads(gzip.decompress(cached).decode("utf8"))

                if res[0]["Has reference"]:
                    if "єдрпоу" not in founder_rec.lower():
                        rec_buffer.append(pk)
                        statements.append([founder_rec, edrpou, "https://ring.org.ua/edr/uk/company/{}".format(edrpou)])
                    else:
                        spoiled_buffer.append(pk)

        # print(Person.objects.filter(pk__in=rec_buffer).update(was_dereferenced=True))

        print(spoiled_buffer)

        with open("/tmp/strange.csv", "w") as fp:
            w = writer(fp)

            w.writerows(sorted(statements, key=lambda x: len(x[0]), reverse=True))

