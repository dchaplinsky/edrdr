import re
import sys
import json
import yaml
import gzip
import redis
import shutil
import os.path
from time import sleep
import logging
from random import randrange
from datetime import datetime

from django.conf import settings
from django.db import connection

from companies.management.commands.load_companies import (
    Command as LoadCommand,
    logger,
    proxies,
    Pipeline
)
from tqdm import tqdm
from dateutil.parser import parse
import requests


class Command(LoadCommand):
    help = (
        "Loads XML with data from registry of companies of Ukraine into " "the database"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--revision",
            help="EDR dump revision to retrieve (leave empty to retrieve latest)",
        )

        parser.add_argument(
            "--guid",
            default="b0476139-62f2-4ede-9d3b-884ad99afd08",
            help="Dataset to retrieve",
        )

        parser.add_argument(
            "--overwrite",
            default=False,
            action="store_true",
            help="Overwrite existing records",
        )

        parser.add_argument(
            "--parser_profile",
            default="pipeline.yaml",
            help="Pipeline configuration file",
        )

    def handle_one_revision_from_new_data_gov(
        self, guid, timestamp, data_url, revision, overwrite=False
    ):
        """
        Process one revision: retrieved from data.gov.ua, parse, unify, load to DB
        """

        _, ext = os.path.splitext(data_url)
        ext = ext or ".zip"

        local_filename = "{}__{}{}".format(
            timestamp.strftime("%d.%m.%Y %H:%M"), revision, ext
        )

        full_path = os.path.join(settings.DATA_STORAGE_PATH, local_filename)

        # Caching it dump file locally to avoid downloading 100Gb over and over again
        if os.path.exists(full_path):
            logger.warning("Skipping {} as it's already exists".format(full_path))
        else:
            r = requests.get(data_url, stream=True)

            with open(full_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)

        with open(full_path, "rb") as fp:
            self.load_file(
                fp,
                guid,
                None,
                timestamp,
                overwrite,
                ext=ext,
                subrevision_id=revision,
                url=data_url,
            )

    def handle(self, *args, **options):
        # Reading parser profile to parse BO and founders using
        # ML power!
        with open(options["parser_profile"], "r") as fp:
            profile = yaml.load(fp.read())

            # Loading the pipeline
            self.pipe = Pipeline(profile["pipeline"])

        # Initializing redis to store extracted named entities in it
        self.redis = redis.StrictRedis.from_url(settings.PARSING_REDIS)
        self.redis_cache_key = "extractor_{}".format(self.pipe.config_key)

        # Retrieving all the datasets we know about
        response = requests.get(
            "https://data.gov.ua/api/3/action/resource_show",
            {"id": options["guid"], "nocache": randrange(100)},
        ).json()

        if not response.get("success"):
            self.stderr.write("Unsuccessful response from api.")
            return

        response["result"]["resource_revisions"].reverse()
        for rev in tqdm(response["result"]["resource_revisions"]):
            revision = rev["url"].strip("/").rsplit("/", 1)[-1]

            if (
                not options["revision"]
                or revision == options["revision"]
                or options["revision"] == "all"
            ):
                timestamp = parse(rev["resource_created"], dayfirst=False)
                if timestamp <= datetime(2018, 10, 24, 0, 0, 0):
                    tqdm.write("Skipping revision {}".format(revision))
                    continue

                data_url = rev["url"]

                tqdm.write("Processing revision {}".format(revision))
                # Revision by revision
                self.handle_one_revision_from_new_data_gov(
                    options["guid"], timestamp, data_url, revision, options["overwrite"]
                )
                sleep(5)

                if options["revision"] != "all":
                    break
