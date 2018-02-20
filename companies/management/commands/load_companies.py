import sys
import json
import re
import redis
import gzip
from pprint import pprint
from tqdm import tqdm
from hashlib import sha1
import shutil
import os.path
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import logging
from time import sleep
from io import TextIOWrapper
from csv import DictReader
from zipfile import ZipFile
from dateutil.parser import parse
from django.conf import settings

sys.path.append(settings.PATH_TO_SECRET_SAUCE)

import yaml
import requests
import requests_cache

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection

from companies.models import Revision, Company, CompanyRecord
from evaluate import Pipeline

if settings.PROXY:
    proxies = { 
        "http": settings.PROXY
    }
else:
    proxies = {}


def whitelist(dct, fields):
    """
    Leave only those fields which keys are present in `fields`

    :param dct: Source dictionary
    :type dct: dict
    :param fields: List of fields to keep
    :type fields: list
    :return: Resulting dictionary containing whitelisted fields only
    :rtype: dict
    """
    return {
        k: v for k, v in dct.items() if k in fields
    }



requests_cache.install_cache('proxied_edr_cache')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reader")


class EDR_Reader(object):
    """
    Simple reader class which allows to iterate over Zipped/not Zipped XML/CSV file
    """

    def __init__(self, in_file, timestamp, revision, file_type="zip"):
        """
        Initializes EDR_Reader class

        :param in_file: file object (zipped or not)
        :type in_file: StringIO or file handler
        :param timestamp: date of export of the file
        :type timestamp: datetime
        :param revision: revision of the dump
        :type revision: string
        :param file_type: type of the file (usually extension)
        :type file_type: string
        """

        self.file = in_file
        self.file_type = file_type
        self.timestamp = timestamp
        self.revision = revision

    def iter_docs(self):
        """
        Reads input file record by record.

        :returns: iterator over company records from registry
        :rtype: collections.Iterable[dict]
        """

        if self.file_type == "zip":
            with ZipFile(self.file) as zip_arch:
                for fname in zip_arch.namelist():
                    if "uo" in fname.lower():
                        logger.info("Reading {} file from archive {}".format(fname, self.file))

                        if fname.lower().endswith(".xml"):
                            with zip_arch.open(fname, 'r') as fp_raw:
                                for l in self._iter_xml(fp_raw):
                                    yield l

                        if fname.lower().endswith(".csv"):
                            with zip_arch.open(fname, 'r') as fp_raw:
                                for l in self._iter_csv(fp_raw):
                                    yield l
        elif self.file_type == "xml":
            for l in self._iter_xml(self.file):
                yield l

        elif self.file_type == "csv":
            for l in self._iter_csv(self.file):
                yield l

    def _iter_xml(self, fp_raw):
        """
        Regex magic is required to
        cover records that was incorrectly exported and incomplete, thus
        make whole XML file invalid (happens sometime)
        """

        with TextIOWrapper(fp_raw, encoding="cp1251") as fp:
            mapping = {
                'NAME': 'name',
                'SHORT_NAME': 'short_name',
                'EDRPOU': 'edrpou',
                'ADDRESS': 'location',
                'BOSS': 'head',
                'KVED': 'company_profile',
                'STAN': 'status',
                'FOUNDERS': 'founders',

                "Найменування": 'name',
                "Скорочена_назва": 'short_name',
                "Код_ЄДРПОУ": 'edrpou',
                "Місцезнаходження": 'location',
                "ПІБ_керівника": 'head',
                "Основний_вид_діяльності": 'company_profile',
                "Стан": 'status',
                "C0": ""
            }

            content = fp.read()
            if "RECORD" in content[:1000]:
                regex = '<RECORD>.*?</RECORD>'
            else:
                regex = '<ROW>.*?</ROW>'

            for i, chunk in enumerate(re.finditer(regex, content, flags=re.S | re.U)):
                company = {}
                founders_list = []
                try:
                    # Fucking ET!
                    etree = ET.fromstring(chunk.group(0).replace("Місцезнаходження", "ADDRESS").encode("utf-8"))
                except ParseError:
                    logger.error('Cannot parse record #{}, {}'.format(i, chunk))
                    continue

                for el in etree.getchildren():
                    field = mapping[el.tag]
                    if field == 'edrpou':
                        if el.text and el.text.lstrip('0'):
                            company[field] = int(el.text)
                        else:
                            company[field] = 0
                    elif field == 'founders':
                        for founder in el.getchildren():
                            founders_list.append(founder.text)
                    else:
                        if field:
                            company[field] = el.text

                company["founders"] = founders_list
                company["last_update"] = self.timestamp
                company["file_revision"] = self.revision

                if i and i % 50000 == 0:
                    logger.debug('Read {} companies from XML feed'.format(i))

                yield company

    def _iter_csv(self, fp_raw):
        with TextIOWrapper(fp_raw, encoding="cp1251") as fp:
            r = DictReader(fp, delimiter=str(";"))

            mapping = {
                "Найменування": 'name',
                "Скорочена назва": 'short_name',
                "Код ЄДРПОУ": 'edrpou',
                "Місцезнаходження": 'location',
                "ПІБ керівника": 'head',
                "Основний вид діяльності": 'company_profile',
                "Стан": 'status',
            }

            for i, chunk in enumerate(r):
                company = {}

                for k, v in chunk.items():
                    if k.strip():
                        if mapping[k] == "edrpou" and v:
                            company[mapping[k]] = int(v)
                        else:
                            company[mapping[k]] = v

                company['founders'] = []
                company["last_update"] = self.timestamp
                company["file_revision"] = self.revision

                if i and i % 50000 == 0:
                    logger.warning('Read {} companies from CSV feed'.format(i))

                yield company


class Command(BaseCommand):
    help = ('Loads XML with data from registry of companies of Ukraine into '
            'the database')

    def add_arguments(self, parser):
        parser.add_argument(
            '--revision',
            help='EDR dump revision to retrieve (leave empty to retrieve latest)',
        )

        parser.add_argument(
            '--guid',
            default="73cfe78e-89ef-4f06-b3ab-eb5f16aea237",
            help='Dataset to retrieve',
        )

        parser.add_argument(
            "--overwrite",
            default=True,
            help="Overwrite existing records"
        )

        parser.add_argument(
            "--parser_profile",
            default="pipeline.yaml",
            help="Pipeline configuration file"
        )
        

    def make_key_for_company(self, company):
        return sha1(
            re.sub(
                "[.,\/#!$%\^&\*;:{}=\-_`~()\s]",
                "",
                "|".join(
                    map(
                        lambda x: (str(x) or "").strip(),
                        [
                            company["name"],
                            company["short_name"],
                            company["location"],
                            company["edrpou"],
                            company.get("company_profile"),
                            company.get("status"),
                        ]
                    )
                ).lower()
            )
            .encode("utf8")
        ).hexdigest()

    def make_key_for_founder(edrpou, founder):
        return sha1(
            re.sub(
                "[.,\/#!$%\^&\*;:{}=\-_`~()\s]",
                "",
                "|".join(
                    map(
                        lambda x: (str(x) or "").strip(),
                        [
                            founder,
                            edrpou
                        ]
                    )
                ).lower()
            )
            .encode("utf8")
        ).hexdigest()

    def handle_one_revision(self, guid, dataset_info, overwrite=False, revision=None):
        try:
            if not revision or revision == dataset_info["revision_id"]:
                timestamp = parse(dataset_info["changed"], dayfirst=True)
                files_list = dataset_info.get("files", [])
            else:
                for rev in dataset_info["revisions"]:
                    if rev["revision_id"] == revision:
                        timestamp = parse(rev["created"], dayfirst=True)
                        break
                else:
                    logger.error("Cannot find revision {} in the dataset {}".format(revision, guid))
                    return

                sleep(1)
                response = requests.get(
                    "http://data.gov.ua/view-dataset/dataset.json",
                    {"dataset-id": guid, "revision-id": revision},
                    proxies=proxies
                ).json()

                files_list = response.get("files", [])
        except (TypeError, IndexError, json.decoder.JSONDecodeError, AttributeError):
            logger.error("Cannot obtain information about dump file, {} {}".format(guid, revision))
            return

        if len(files_list) != 1:
            logger.warning("Too many files in API response, trying to find a proper one")
            for f in files_list:
                if "uo" in f["url"].lower():
                    files_list = [f]
                    break
            else:
                logger.error("Nothing suitable found, {} {}".format(guid, revision))
                return

        dump = files_list[0]
        _, ext = os.path.splitext(dump["url"])

        local_filename = "{}__{}{}".format(timestamp.strftime("%d.%m.%Y %H:%M"), revision, ext)

        full_path = os.path.join(settings.DATA_STORAGE_PATH, local_filename)

        if os.path.exists(full_path):
            logger.warning("Skipping {} as it's already exists".format(full_path))
        else:
            r = requests.get(dump["url"], stream=True)

            with open(full_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        with open(full_path, 'rb') as fp:
            revision, revision_created = Revision.objects.get_or_create(
                pk=revision,
                defaults={
                    "dataset_id": guid,
                    "created": timestamp,
                    "url": dump["url"]
                }
            )

            if revision.imported and not overwrite:
                logger.warning("Revision {}, file {} was already imported successfully, skipping".format(
                    revision.revision_id, revision.url))
                return

            reader = EDR_Reader(fp, timestamp, revision, ext.lower().lstrip("."))
            companies_in_bd = set(Company.objects.values_list("pk", flat=True))
            company_records_in_bd = set(CompanyRecord.objects.values_list("pk", flat=True))

            company_records_with_no_revision = set(
                CompanyRecord.objects.filter(revisions__contains=[revision.pk]).values_list("pk", flat=True)
            )

            company_records_to_add_revision = []

            companies_to_create = []
            company_records_to_create = []
            with tqdm() as pbar:
                for company_line in reader.iter_docs():
                    pbar.update(1)

                    if company_line["edrpou"] == 0 or isinstance(company_line["edrpou"], str):
                        continue

                    if company_line.get("founders"):
                        founders = self.parse_raw_rec(company_line)

                    if company_line["edrpou"] not in companies_in_bd:
                        companies_to_create.append(Company(edrpou=company_line["edrpou"]))
                        companies_in_bd.add(company_line["edrpou"])

                    company_hash = self.make_key_for_company(company_line)
                    if company_hash not in company_records_in_bd:
                        company_record = CompanyRecord(
                            company_hash=company_hash,
                            company_id=company_line["edrpou"],
                            name=company_line["name"],
                            short_name=company_line["short_name"] or "",
                            location=company_line["location"] or "",
                            company_profile=company_line.get("company_profile", "") or "",
                            status=CompanyRecord.get_status(company_line.get("status", "інформація відсутня")),
                            revisions=[revision.pk]
                        )

                        company_records_to_create.append(company_record)
                        company_records_in_bd.add(company_hash)
                    else:
                        if company_hash not in company_records_with_no_revision:
                            company_records_to_add_revision.append(company_hash)
                            company_records_with_no_revision.add(company_hash)

                    if len(companies_to_create) >= 10000:
                        Company.objects.bulk_create(companies_to_create)
                        CompanyRecord.objects.bulk_create(company_records_to_create)
                        companies_to_create = []
                        company_records_to_create = []

                    if len(company_records_to_add_revision) >= 10000:
                        with connection.cursor() as cursor:
                            # Fuck, cannot believe I'm doing that
                            hashes_str = ",".join("'{}'".format(s) for s in company_records_to_add_revision)
                            # Guess what? There are no support of adding something to PG arrays through django ORM
                            cursor.execute(
                                "UPDATE " + CompanyRecord._meta.db_table + "  SET revisions = revisions || '{%s}' " +
                                "WHERE company_hash IN (" + hashes_str + ")",
                                [int(revision.pk)]
                            )

                        company_records_to_add_revision = []

            if companies_to_create:
                Company.objects.bulk_create(companies_to_create)

            if company_records_to_create:
                CompanyRecord.objects.bulk_create(company_records_to_create)

            if company_records_to_add_revision:
                with connection.cursor() as cursor:
                    # Fuck, cannot believe I'm doing that
                    hashes_str = ",".join("'{}'".format(s) for s in company_records_to_add_revision)
                    # Guess what? There are no support of adding something to PG arrays through django ORM
                    cursor.execute(
                        "UPDATE " + CompanyRecord._meta.db_table + "  SET revisions = revisions || '{%s}' " +
                        "WHERE company_hash IN (" + hashes_str + ")",
                        [int(revision.pk)]
                    )

            revision.imported = True
            revision.save()

    def parse_raw_rec(self, company):
        rec_hash = sha1("".join(company["founders"]).lower().encode("utf8")).hexdigest()

        cached = self.redis.hget(self.redis_cache_key, rec_hash)

        if cached is None:
            result = [
                whitelist(
                    r,
                    [
                        "Is beneficial owner", "BO is absent", "Has reference",
                        "Was dereferenced", "Name", "Country of residence", "Address of residence"
                    ]
                )
                for r in self.pipe.transform_company(company)
            ]

            self.redis.hset(
                self.redis_cache_key,
                rec_hash,
                gzip.compress(json.dumps(result).encode("utf8"))
            )

            return result 
        else:
            res = json.loads(gzip.decompress(cached).decode("utf8"))
            return res


    def handle(self, *args, **options):
        with open(options["parser_profile"], "r") as fp:
            profile = yaml.load(fp.read())

            self.pipe = Pipeline(profile["pipeline"])

        self.redis = redis.StrictRedis.from_url(settings.PARSING_REDIS)
        self.redis_cache_key = "extractor_{}".format(self.pipe.config_key)

        if options["guid"] == "all":
            logger.info("Retrieving all datasets we know about")
            guids = ["73cfe78e-89ef-4f06-b3ab-eb5f16aea237", "5fc89a6f-55b8-4ec6-95d6-38a0fdc31be1"]
        else:
            guids = [options["guid"]]

        for guid in tqdm(guids):
            dataset_info = requests.get(
                "http://data.gov.ua/view-dataset/dataset.json",
                {"dataset-id": guid},
                proxies=proxies
            ).json()

            if options["revision"] is None:
                revisions = [dataset_info["revision_id"]]
            elif options["revision"] == "all":
                revisions = [dataset_info["revision_id"]] + list(
                    x["revision_id"] for x in dataset_info["revisions"]
                )
                logger.info("Retrieving all {} revisions for dataset {}".format(
                    len(revisions), guid
                ))
            else:
                revisions = [options["revision"]]

            for r in tqdm(revisions):
                sleep(5)
                self.handle_one_revision(guid, dataset_info, options["overwrite"], revision=r)
