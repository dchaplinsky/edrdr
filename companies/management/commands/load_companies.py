import re
import sys
import json
import yaml
import gzip
import redis
import shutil
import os.path
import logging
import xml.etree.ElementTree as ET
from itertools import islice
from time import sleep
from hashlib import sha1
from csv import DictReader
from zipfile import ZipFile
from io import TextIOWrapper
from random import randrange

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.core.management.base import BaseCommand

from tqdm import tqdm
from dateutil.parser import parse
import requests
import requests_cache


from companies.models import Revision, Company, CompanyRecord, Person
sys.path.append(settings.PATH_TO_SECRET_SAUCE)
from evaluate import Pipeline

if settings.PROXY:
    proxies = {
        "http": settings.PROXY,
        "https": settings.PROXY
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


def chunkify(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())

# requests_cache.install_cache('proxied_edr_cache')

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
        Iterate over XML file (usually EDR dumps are exported in XML, which,
        howerver, might have different field names, that's covered by mapping
        below)
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
                except ET.ParseError:
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
                        if field and field in mapping:
                            company[field] = el.text

                company["founders"] = founders_list
                company["last_update"] = self.timestamp
                company["file_revision"] = self.revision

                if i and i % 50000 == 0:
                    logger.debug('Read {} companies from XML feed'.format(i))

                yield company

    def _iter_csv(self, fp_raw):
        """
        Iterate over CSV file (some old dumps were exported in CSV)
        """
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
            default=False,
            action="store_true",
            help="Overwrite existing records"
        )

        parser.add_argument(
            "--local_file",
            help="Load data from a local file"
        )

        parser.add_argument(
            "--parser_profile",
            default="pipeline.yaml",
            help="Pipeline configuration file"
        )

        parser.add_argument(
            "--timestamp",
            help="Local file timestamp"
        )

    def make_key_for_company(self, company):
        """
        That's sha1 key for company record built out of
        company name/shortname, location, edrpou and other fields
        """
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

    def make_key_for_person(self, edrpou, raw_description, position):
        """
        That's sha1 key for person record built out of
        company edrpou and some raw text and position
        """
        return sha1(
            re.sub(
                "[.,\/#!$%\^&\*;:{}=\-_`~()\s]",
                "",
                "|".join(
                    map(
                        lambda x: (str(x) or "").strip(),
                        [
                            raw_description,
                            edrpou,
                            position
                        ]
                    )
                ).lower()
            )
            .encode("utf8")
        ).hexdigest()

    def handle_one_revision_from_old_data_gov(self, guid, dataset_info, overwrite=False, revision=None):
        """
        Process one revision: retrieved from data.gov.ua, parse, unify, load to DB
        """
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

        # Caching it dump file locally to avoid downloading 100Gb over and over again
        if os.path.exists(full_path):
            logger.warning("Skipping {} as it's already exists".format(full_path))
        else:
            r = requests.get(dump["url"], stream=True)

            with open(full_path, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        with open(full_path, 'rb') as fp:
            self.load_file(fp, guid, revision, timestamp, overwrite, ext=ext, url=data_url)

    @staticmethod
    def cleanup_countries(list_of_countries):
        return list(
            set(
                filter(
                    lambda x: x not in ["пряме", "прямий", "республіка", "причина", "флорида", "лакатамія"],
                    map(str.strip, list_of_countries),
                )
            )
        )

    def load_file(self, fp, guid, revision_id, timestamp, overwrite, ext, subrevision_id=None, url=""):
        # At first, let's try to create Revision. Revision is a single dump
        # file retrieved from data.gov.ua. Revision id is unique even across
        # different datasets

        if revision_id is not None:
            revision, revision_created = Revision.objects.get_or_create(
                pk=revision_id,
                defaults={
                    "dataset_id": guid,
                    "created": timestamp,
                    "url": url
                }
            )
        elif subrevision_id is not None:
            revision, revision_created = Revision.objects.get_or_create(
                subrevision_id=subrevision_id,
                defaults={
                    "dataset_id": guid,
                    "created": timestamp,
                    "url": url
                }
            )
        else:
            return

        # If it's already in database and marked as fully imported we skip it
        # unless overwrite flag is set to True
        if revision.imported and not overwrite:
            logger.warning("Revision {}, file {} was already imported successfully, skipping".format(
                revision.revision_id, revision.url))
            return

        reader = EDR_Reader(fp, timestamp, revision, ext.lower().lstrip("."))
        # To avoid hitting DB we first will pre-cache ids of companies and company records in db
        # Where company is an entity, and the company record is the state of that entity in a given period
        # of time
        companies_in_bd = set(Company.objects.values_list("pk", flat=True))
        company_records_in_bd = set(CompanyRecord.objects.values_list("company_hash", flat=True))

        # list of company records where current revision is already set
        company_records_with_no_revision = set(
            CompanyRecord.objects.filter(revisions__contains=[revision.pk]).values_list("company_hash", flat=True)
        )

        # Accumulator for the company records to set current revision in bulk
        company_records_to_add_revision = []

        # List of persons that is already in db
        persons_in_bd = set(Person.objects.values_list("person_hash", flat=True))
        # list of persons where current revision is already set
        persons_with_no_revision = set(
            Person.objects.filter(revisions__contains=[revision.pk]).values_list("person_hash", flat=True)
        )
        # Accumulator for the persons to set current revision in bulk
        persons_to_add_revision = []

        # Accumulator for the companies to create in bulk
        companies_to_create = []
        # Accumulator for the company records to create in bulk
        company_records_to_create = []

        # Companies to mark for parsing/reindexing
        dirty_companies = set()

        # Accumulator for the persons to create in bulk
        persons_to_create = []
        with tqdm() as pbar:
            for company_line in reader.iter_docs():
                pbar.update(1)

                # Basic sanity checks
                if company_line["edrpou"] == 0 or isinstance(company_line["edrpou"], str):
                    continue

                if company_line.get("head", ""):
                    head_hash = self.make_key_for_person(
                        company_line["edrpou"],
                        company_line["head"],
                        "head"
                    )
                    if head_hash not in persons_in_bd:
                        person = Person(
                            company_id=company_line["edrpou"],
                            person_type="head",
                            person_hash=head_hash,
                            raw_record=company_line["head"],
                            name=[company_line["head"]],
                            revisions=[revision.pk],
                        )
                        persons_to_create.append(person)
                        dirty_companies.add(company_line["edrpou"])
                        persons_in_bd.add(head_hash)
                    else:
                        if head_hash not in persons_with_no_revision:
                            persons_to_add_revision.append(head_hash)
                            persons_with_no_revision.add(head_hash)

                # Parsing founder records
                if company_line.get("founders"):
                    founders = self.parse_raw_rec(company_line)

                    for f in founders:
                        if f["Is beneficial owner"]:
                            # That's BO and we know a name
                            bo_hash = self.make_key_for_person(
                                company_line["edrpou"],
                                f["raw_record"],
                                "owner"
                            )

                            if bo_hash not in persons_in_bd:
                                person = Person(
                                    company_id=company_line["edrpou"],
                                    person_type="owner",
                                    person_hash=bo_hash,
                                    raw_record=f["raw_record"],
                                    name=list(set(map(str.strip, f["Name"]))),
                                    address=f["Address of residence"],
                                    country=self.cleanup_countries(f["Country of residence"]),
                                    revisions=[revision.pk],
                                    bo_is_absent=f["BO is absent"],
                                )
                                persons_to_create.append(person)
                                dirty_companies.add(company_line["edrpou"])
                                persons_in_bd.add(bo_hash)
                            else:
                                if bo_hash not in persons_with_no_revision:
                                    persons_to_add_revision.append(bo_hash)
                                    persons_with_no_revision.add(bo_hash)
                        else:
                            founder_hash = self.make_key_for_person(
                                company_line["edrpou"],
                                f["raw_record"],
                                "owner"
                            )

                            if founder_hash not in persons_in_bd:
                                person = Person(
                                    company_id=company_line["edrpou"],
                                    person_hash=founder_hash,
                                    person_type="founder",
                                    raw_record=f["raw_record"],
                                    name=list(set(map(str.strip, f["Name"]))),
                                    address=f["Address of residence"],
                                    country=self.cleanup_countries(f["Country of residence"]),
                                    revisions=[revision.pk],
                                )
                                persons_to_create.append(person)
                                persons_in_bd.add(founder_hash)
                            else:
                                if founder_hash not in persons_with_no_revision:
                                    persons_to_add_revision.append(founder_hash)
                                    persons_with_no_revision.add(founder_hash)

                # If company is not in db yet, let's add it to the accum
                if company_line["edrpou"] not in companies_in_bd:
                    companies_to_create.append(Company(edrpou=company_line["edrpou"]))
                    dirty_companies.add(company_line["edrpou"])
                    companies_in_bd.add(company_line["edrpou"])

                # Checking if such company record is already present in db
                company_record_hash = self.make_key_for_company(company_line)
                if company_record_hash not in company_records_in_bd:
                    company_record = CompanyRecord(
                        company_hash=company_record_hash,
                        company_id=company_line["edrpou"],
                        name=company_line["name"],
                        short_name=company_line["short_name"] or "",
                        location=company_line["location"] or "",
                        company_profile=company_line.get("company_profile", "") or "",
                        status=CompanyRecord.get_status(company_line.get("status", "інформація відсутня")),
                        revisions=[revision.pk]
                    )

                    # Adding that company into accum
                    company_records_to_create.append(company_record)
                    dirty_companies.add(company_line["edrpou"])
                    # Ignoring that company record hash for the current revision
                    company_records_in_bd.add(company_record_hash)
                else:
                    if company_record_hash not in company_records_with_no_revision:
                        company_records_to_add_revision.append(company_record_hash)
                        company_records_with_no_revision.add(company_record_hash)

                if len(companies_to_create) >= 10000 or len(persons_to_create) >= 10000:
                    Company.objects.bulk_create(companies_to_create)
                    CompanyRecord.objects.bulk_create(company_records_to_create)
                    companies_to_create = []
                    company_records_to_create = []

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

                        company_records_to_add_revision = []

                if len(persons_to_create) >= 10000:
                    Person.objects.bulk_create(persons_to_create)
                    persons_to_create = []

                    if persons_to_add_revision:
                        with connection.cursor() as cursor:
                            hashes_str = ",".join("'{}'".format(s) for s in persons_to_add_revision)
                            cursor.execute(
                                "UPDATE " + Person._meta.db_table + "  SET revisions = revisions || '{%s}' " +
                                "WHERE person_hash IN (" + hashes_str + ")",
                                [int(revision.pk)]
                            )

                        persons_to_add_revision = []

        if companies_to_create:
            Company.objects.bulk_create(companies_to_create)

        if company_records_to_create:
            CompanyRecord.objects.bulk_create(company_records_to_create)

        if persons_to_create:
            Person.objects.bulk_create(persons_to_create)

        if company_records_to_add_revision:
            with connection.cursor() as cursor:
                hashes_str = ",".join("'{}'".format(s) for s in company_records_to_add_revision)
                cursor.execute(
                    "UPDATE " + CompanyRecord._meta.db_table + "  SET revisions = revisions || '{%s}' " +
                    "WHERE company_hash IN (" + hashes_str + ")",
                    [int(revision.pk)]
                )

        if persons_to_add_revision:
            with connection.cursor() as cursor:
                hashes_str = ",".join("'{}'".format(s) for s in persons_to_add_revision)
                cursor.execute(
                    "UPDATE " + Person._meta.db_table + "  SET revisions = revisions || '{%s}' " +
                    "WHERE person_hash IN (" + hashes_str + ")",
                    [int(revision.pk)]
                )

        if dirty_companies:
            for update_me in chunkify(dirty_companies, 10000):
                logger.debug(
                    "Updating {} records in db as dirty".format(len(update_me))
                )
                Company.objects.filter(pk__in=update_me).update(
                    is_dirty=True, last_modified=timezone.now()
                )

        revision.imported = True
        revision.save()

    def parse_raw_rec(self, company):
        """
        That's just a glue to make edr parser work with all the data + extra layer
        of caching
        """

        parsed = []

        for founder_rec in company.get("founders", []) or []:
            rec_hash = sha1(founder_rec.lower().encode("utf8")).hexdigest()

            cached = self.redis.hget(self.redis_cache_key, rec_hash)

            company_mock = company.copy()
            company_mock["founders"] = [founder_rec]

            if cached is None:
                result = []

                # Call the magic sauce!
                for r in self.pipe.transform_company(company_mock):
                    r["raw_record"] = founder_rec

                    result = [
                        whitelist(
                            r,
                            [
                                "Is beneficial owner", "BO is absent", "Has reference",
                                "Was dereferenced", "Name", "Country of residence",
                                "Address of residence", "raw_record"
                            ]
                        )
                    ]

                self.redis.hset(
                    self.redis_cache_key,
                    rec_hash,
                    # Whoooo, we even have gzip compression
                    gzip.compress(json.dumps(result).encode("utf8"))
                )

                parsed.append(result)
            else:
                res = json.loads(gzip.decompress(cached).decode("utf8"))
                parsed.append(res)

        return [subp for p in parsed for subp in p]

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

        if options["local_file"]:
            _, ext = os.path.splitext(options["local_file"])

            with open(options["local_file"], "rb") as fp:
                self.load_file(
                    fp,
                    options["guid"],
                    options["revision"],
                    parse(options["timestamp"], dayfirst=True),
                    options["overwrite"],
                    ext=ext,
                    url=""
                )
        else:
            if options["guid"] == "all":
                logger.info("Retrieving all datasets we know about")
                guids = ["73cfe78e-89ef-4f06-b3ab-eb5f16aea237", "5fc89a6f-55b8-4ec6-95d6-38a0fdc31be1"]
            else:
                guids = [options["guid"]]

            # Retrieving all the datasets we know about
            for guid in tqdm(guids):
                dataset_info = requests.get(
                    "http://data.gov.ua/view-dataset/dataset.json",
                    {"dataset-id": guid, "cachebuster": randrange(10)},
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
                    # Revision by revision
                    self.handle_one_revision_from_old_data_gov(guid, dataset_info, options["overwrite"], revision=r)
