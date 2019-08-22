import re
import logging
from functools import reduce
from itertools import permutations, product, islice
from operator import mul

from collections import OrderedDict, defaultdict
from django.db import models
from django.utils.translation import ugettext_noop as _
from django.contrib.postgres.fields import ArrayField, JSONField
from django.urls import reverse
from django.forms.models import model_to_dict
from Levenshtein import jaro
from fuzzywuzzy import fuzz
from tokenize_uk import tokenize_words
from companies.exceptions import StatusDoesntExist, TooManyVariantsError

from names_translator.name_utils import parse_and_generate, autocomplete_suggestions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("models")


class Revision(models.Model):
    revision_id = models.AutoField("Номер ревізії", primary_key=True)
    subrevision_id = models.CharField(
        "Дурна ревізія з нового сайту data.gov.ua", max_length=20, default=""
    )
    dataset_id = models.TextField("Датасет")
    created = models.DateTimeField("Дата створення")
    imported = models.BooleanField("Імпорт завершено", default=False)
    ignore = models.BooleanField("Ігнорувати через помилки імпорту", default=False)
    url = models.URLField("Посилання на набір данних")

    def get_absolute_url(self):
        return reverse("revision>detail", kwargs={"pk": self.pk})


class Company(models.Model):
    edrpou = models.IntegerField(primary_key=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_dirty = models.BooleanField(
        "Потребує повторної індексації", db_index=True, default=True
    )

    status_order = (
        "зареєстровано",
        "зареєстровано, свідоцтво про державну реєстрацію недійсне",
        "порушено справу про банкрутство",
        "порушено справу про банкрутство (санація)",
        "в стані припинення",
        "припинено",
    )

    CRIMEA_MARKERS = [
        re.compile(s, flags=re.U | re.I) for s in [r"\bАРК\b", r"\bКрим\b"]
    ]

    DONETSK_MARKER_LEVEL1 = [
        re.compile(s, flags=re.U | re.I) for s in [r"\bДонецк", r"\bДонецьк"]
    ]

    DONETSK_MARKER_LEVEL2 = [
        re.compile(r"\b{}\b".format(s), flags=re.U | re.I)
        for s in [
            "Авдіївка",
            "Адвеевка",
            "Горлівка",
            "Горловка",
            "Донецьк",
            "Донецк",
            "Єнакієве",
            "Енакиево",
            "Жданівка",
            "Ждановка",
            "Макіївка",
            "Макеевка",
            "Сніжне",
            "Снежное",
            "Харцизьк",
            "Харцызск",
            "Хрестівка",
            "Чистякове",
            "Чистяково",
            "Шахтарськ",
            "Шахтерск",
            "Ясинувата",
            "Ясиноватая",
            "Дебальцеве",
            "Дебальцево",
        ]
    ]

    LUHANSK_MARKER_LEVEL1 = [
        re.compile(s, flags=re.U | re.I) for s in [r"\bЛуганськ", r"\bЛуганск"]
    ]

    LUHANSK_MARKER_LEVEL2 = [
        re.compile(r"\b{}\b".format(s), flags=re.U | re.I)
        for s in [
            "Алчевськ",
            "Алчевск",
            "Антрацит",
            "Брянка",
            "Голубівка",
            "Голубевка",
            "Довжанськ",
            "Должанск",
            "Кадіївка",
            "Кадиевка",
            "Луганськ",
            "Луганск",
            "Первомайськ",
            "Первомайск",
            "Ровеньки",
            "Сорокине",
            "Сорокино",
            "Хрустальний",
            "Хрустальный",
            "Золоте",
            "Золотое",
        ]
    ]

    @property
    def full_edrpou(self):
        return str(self.pk).rjust(8, "0")

    def get_absolute_url(self):
        return reverse("company>detail", kwargs={"pk": self.full_edrpou})

    @staticmethod
    def compare_two_names(name1, name2, max_splits=7):
        name1 = re.sub(r"\s+", " ", name1.lower().strip())
        name2 = re.sub(r"\s+", " ", name2.lower().strip())
        splits = name2.split(" ")
        limit = reduce(mul, range(1, max_splits + 1))

        if len(splits) > max_splits:
            print("Too much permutations for {}".format(name2))

        return max(
            jaro(name1, " ".join(opt)) for opt in islice(permutations(splits), limit)
        )

    @staticmethod
    def compare_two_list_of_names(list_a, list_b, cutoff=0.93):
        result = []

        if len(list_a) * len(list_b) > 1000:
            raise TooManyVariantsError()

        for i, (side_a, side_b) in enumerate(product(list_a, list_b)):
            if side_a == side_b:
                continue

            score = Company.compare_two_names(side_a, side_b)
            if score > cutoff:
                result.append({"side_a": side_a, "side_b": side_b, "score": score})

            if i > 1000:
                break

        return result

    @staticmethod
    def ugly_strip(s):
        return s.strip(' -.’,0"139472856)/;№&`%+“‘”*¦:\'').strip().lower()

    def take_snapshot_of_flags(
        self, revision=None, force=False, mass_registration=None
    ):
        if revision is None:
            revision = Revision.objects.order_by("-created").first()
        else:
            revision = Revision.objects.get(revision)

        if mass_registration is None:
            mass_registration = CompanyRecord.objects.mass_registration_addresses(
                revision=revision.pk
            )

        # Let the rampage begin
        existing_snapshot = CompanySnapshotFlags.objects.filter(
            company=self, revision=revision
        )
        if existing_snapshot:
            if force:
                snapshot = existing_snapshot.first()

                # Resetting existing values
                snapshot.has_bo = False
                snapshot.has_bo_companies = False
                snapshot.has_bo_persons = False
                snapshot.has_founder_companies = False
                snapshot.has_founder_persons = False
                snapshot.has_only_companies_bo = False
                snapshot.has_only_companies_founder = False
                snapshot.has_only_persons_bo = False
                snapshot.has_only_persons_founder = False
                snapshot.has_same_person_as_bo_and_founder = False
                snapshot.has_same_person_as_bo_and_head = False
                snapshot.has_very_similar_person_as_bo_and_founder = False
                snapshot.has_very_similar_person_as_bo_and_head = False
                snapshot.has_bo_on_occupied_soil = False
                snapshot.has_bo_in_crimea = False
                snapshot.acting_and_explicitly_stated_that_has_no_bo = False
                snapshot.has_mass_registration_address = False
                snapshot.has_changes_in_bo = False
                snapshot.has_changes_in_ownership = False
                snapshot.has_pep_owner = False
                snapshot.had_pep_owner_in_the_past = False
                snapshot.has_undeclared_pep_owner = False
                snapshot.has_discrepancy_with_declarations = False
                snapshot.self_owned = False
                snapshot.indirectly_self_owned = False
                snapshot.has_same_person_as_head_and_founder = False
            else:
                return
        else:
            snapshot = CompanySnapshotFlags(company=self, revision=revision)

        latest_record = CompanyRecord.objects.filter(
            company=self, revisions__contains=[revision.pk]
        ).first()

        company_is_acting = False
        if not latest_record:
            snapshot.not_present_in_revision = True
        else:
            company_is_acting = latest_record.status == 1
            snapshot.has_mass_registration_address = (
                latest_record.shortened_validated_location in mass_registration
            )

        persons = Person.objects.filter(company=self, revisions__contains=[revision.pk])

        all_founder_persons = set()
        all_owner_persons = set()
        all_head_persons = set()
        all_bo_countries = set()
        all_founder_countries = set()

        for p in persons:
            if p.person_type == "owner":
                snapshot.has_bo = True
                all_bo_countries |= set(p.country)

                if p.bo_is_absent and company_is_acting:
                    snapshot.acting_and_explicitly_stated_that_has_no_bo = True

                if p.name:
                    snapshot.has_bo_persons = True
                    all_owner_persons |= set(map(self.ugly_strip, p.name))
                else:
                    if p.was_dereferenced:
                        snapshot.has_dereferenced_bo = True
                    else:
                        snapshot.has_bo_companies = True

                for addr in p.address:
                    for r in self.CRIMEA_MARKERS:
                        if r.search(addr):
                            snapshot.has_bo_in_crimea = True
                            break

                    for r1 in self.LUHANSK_MARKER_LEVEL1:
                        if r1.search(addr):
                            for r2 in self.LUHANSK_MARKER_LEVEL2:
                                if r2.search(addr):
                                    snapshot.has_bo_on_occupied_soil = True
                                    break

                    for r1 in self.DONETSK_MARKER_LEVEL1:
                        if r1.search(addr):
                            for r2 in self.DONETSK_MARKER_LEVEL2:
                                if r2.search(addr):
                                    snapshot.has_bo_on_occupied_soil = True
                                    break

            if p.person_type == "founder":
                all_founder_countries |= set(p.country)
                if p.name:
                    snapshot.has_founder_persons = True
                    all_founder_persons |= set(map(self.ugly_strip, p.name))
                else:
                    snapshot.has_founder_companies = True

            if p.person_type == "head":
                if p.name:
                    all_head_persons |= set(map(self.ugly_strip, p.name))

        if snapshot.has_bo_persons:
            grouped_records = self.get_grouped_record(
                persons_filter_clause=models.Q(person_type__in=["owner", "founder"])
            )["grouped_persons_records"]

            prev_names = {"founder": None, "owner": None}

            flags_mapping = {
                "owner": {
                    "flag_field": "has_changes_in_ownership",
                    "diff_field": "ownership_diff",
                },
                "founder": {"flag_field": "has_changes_in_bo", "diff_field": "bo_diff"},
            }

            for group in grouped_records:
                names = {"founder": set(), "owner": set()}

                for r in group["record"]:
                    names[r.person_type] |= set(map(self.ugly_strip, r.name))

                for k in flags_mapping:
                    if prev_names[k] is not None and names[k] != prev_names[k]:
                        on_the_left = prev_names[k] - names[k]
                        on_the_right = names[k] - prev_names[k]

                        if len(on_the_left) == len(on_the_right):
                            ratio = fuzz.token_set_ratio(
                                " ".join(on_the_left), " ".join(on_the_right)
                            )
                            if ratio >= 90:
                                pass
                            else:
                                setattr(snapshot, flags_mapping[k]["flag_field"], True)
                                setattr(
                                    snapshot,
                                    flags_mapping[k]["diff_field"],
                                    {
                                        "prev": list(on_the_left),
                                        "next": list(on_the_right),
                                        "ratio": ratio,
                                    },
                                )
                        else:
                            setattr(snapshot, flags_mapping[k]["flag_field"], True)
                            setattr(
                                snapshot,
                                flags_mapping[k]["diff_field"],
                                {
                                    "prev": list(on_the_left),
                                    "next": list(on_the_right),
                                    "ratio": 100,
                                },
                            )

                prev_names = names
                if snapshot.has_changes_in_bo and snapshot.has_changes_in_ownership:
                    break

        if snapshot.has_bo_persons and not snapshot.has_bo_companies:
            snapshot.has_only_persons_bo = True

        if snapshot.has_bo_companies and not snapshot.has_bo_persons:
            snapshot.has_only_companies_bo = True

        if snapshot.has_founder_persons and not snapshot.has_founder_companies:
            snapshot.has_only_persons_founder = True

        if snapshot.has_founder_companies and not snapshot.has_founder_persons:
            snapshot.has_only_companies_founder = True

        if all_owner_persons & all_founder_persons:
            snapshot.has_same_person_as_bo_and_founder = True

        if all_owner_persons & all_head_persons:
            snapshot.has_same_person_as_bo_and_head = True

        if all_founder_persons & all_head_persons:
            snapshot.has_same_person_as_head_and_founder = True

        snapshot.all_similar_founders_and_bos = []
        try:
            found_something = self.compare_two_list_of_names(
                all_founder_persons, all_owner_persons
            )
            if found_something:
                snapshot.all_similar_founders_and_bos = found_something
                snapshot.has_very_similar_person_as_bo_and_founder = True
        except TooManyVariantsError:
            print("Too many persons to compare for company {}".format(self.pk))

        snapshot.all_similar_heads_and_bos = []
        try:
            found_something = self.compare_two_list_of_names(
                all_head_persons, all_owner_persons
            )
            if found_something:
                snapshot.all_similar_heads_and_bos = found_something
                snapshot.has_very_similar_person_as_bo_and_head = True
        except TooManyVariantsError:
            print("Too many persons to compare for company {}".format(self.pk))

        snapshot.all_similar_heads_and_founders = []
        try:
            found_something = self.compare_two_list_of_names(
                all_head_persons, all_founder_persons
            )
            if found_something:
                snapshot.all_similar_heads_and_founders = found_something
                snapshot.has_very_similar_person_as_head_and_founder = True
        except TooManyVariantsError:
            print("Too many persons to compare for company {}".format(self.pk))

        snapshot.all_owner_persons = list(all_owner_persons)
        snapshot.all_founder_persons = list(all_founder_persons)
        snapshot.all_bo_countries = list(all_bo_countries)
        snapshot.all_founder_countries = list(all_founder_countries)

        if self.peps.filter(years__contains=[2018], from_declaration=True).exists():
            snapshot.has_pep_owner = True
            pep_bo = self.peps.filter(years__contains=[2018], from_declaration=True).first()

            for person in all_owner_persons:
                if self.compare_two_names(person, pep_bo.person) > 0.93:
                    break
            else:
                snapshot.has_discrepancy_with_declarations = True

        if self.peps.filter(from_declaration=True).exclude(years__contains=[2018]).exists():
            snapshot.had_pep_owner_in_the_past = True

        if self.peps.filter(from_declaration=False).exists():
            snapshot.has_undeclared_pep_owner = True

        if self.self_owned.filter(level=1).exists():
            snapshot.self_owned = True

        if self.self_owned.filter(level__gt=1).exists():
            snapshot.indirectly_self_owned = True

        snapshot.save()

    def to_dict(self):
        addresses = set()
        persons = set()
        all_persons = set()
        names_autocomplete = set()
        companies = set()
        company_profiles = set()
        raw_records = set()

        companies.add(self.full_edrpou)
        companies.add(str(self.pk))

        latest_record = None
        latest_revision = 0
        for company_record in (
            self.records.all()
            .defer("company_hash", "location_parsing_quality")
            .nocache()
        ):
            addresses.add(company_record.location)
            addresses.add(company_record.parsed_location)
            addresses.add(company_record.validated_location)

            company_profiles.add(company_record.company_profile)
            companies.add(company_record.name)

            names_autocomplete.add(company_record.name)
            names_autocomplete.add(company_record.short_name)
            names_autocomplete.add(self.full_edrpou)
            names_autocomplete.add(str(self.pk))

            companies.add(company_record.short_name)

            if company_record.revisions:
                if max(company_record.revisions) > latest_revision:
                    latest_record = company_record
                    latest_revision = max(company_record.revisions)
            else:
                logger.warning(
                    "Cannot find revisions for the CompanyRecord {}".format(self.pk)
                )

        for person in (
            self.persons.all().defer("tokenized_record", "share", "revisions").nocache()
        ):
            for name in person.name:
                persons.add((name, person.get_person_type_display()))

                for addr in person.address:
                    addresses.add(addr)

                for country in person.country:
                    addresses.add(country)

            raw_records.add(person.raw_record)

        for name, position in persons:
            all_persons |= parse_and_generate(name, position)
            names_autocomplete |= autocomplete_suggestions(name)

        return {
            "full_edrpou": self.full_edrpou,
            "addresses": list(filter(None, addresses)),
            "persons": list(filter(None, all_persons)),
            "companies": list(filter(None, companies)),
            "company_profiles": list(filter(None, company_profiles)),
            "latest_record": latest_record.to_dict(),
            "raw_records": list(filter(None, raw_records)),
            "names_autocomplete": list(filter(None, names_autocomplete)),
        }

    def group_revisions(self, revisions, records, hash_field_getter):
        periods = []
        current_record = None

        current_hash = None
        start_revision = None
        finish_revision = None

        def add_group(current_record):
            if current_record is not None:
                periods.append(
                    {
                        "start_revision": start_revision,
                        "finish_revision": finish_revision,
                        "record": current_record,
                    }
                )
            current_record = None

        for r, revision in revisions.items():
            rec = records.get(r)
            if rec is None:
                if current_hash is not None:
                    # Record disappeared from a history at some point
                    add_group(current_record)
                    current_hash = None
                    start_revision = revision
                    finish_revision = revision
                else:
                    start_revision = revision
                    finish_revision = revision
                    # Record for that company wasn't
                    # present at the time of given revision
                continue

            if current_hash == hash_field_getter(rec):
                # If nothing changed between two consequent revisions
                # adding current record to the group
                finish_revision = revision
            else:
                add_group(current_record)
                current_record = rec
                current_hash = hash_field_getter(rec)
                start_revision = revision
                finish_revision = revision

        add_group(current_record)

        return periods

    def key_by_company_status(self, obj):
        try:
            return self.status_order.index(obj.get_status_display().lower())
        except ValueError:
            return -len(self.status_order)

    def get_grouped_record(self, persons_filter_clause=models.Q(bo_is_absent=False)):
        used_revisions = set()
        latest_record = None
        latest_record_revision = 0
        records_revisions = defaultdict(list)

        latest_persons = []
        latest_persons_revision = 0
        global_revisions = OrderedDict(
            [
                (r.pk, r)
                for r in Revision.objects.filter(imported=True, ignore=False).order_by(
                    "pk"
                )
            ]
        )

        for rec in self.records.all():
            for r in rec.revisions:
                if r in records_revisions:
                    records_revisions[r].append(rec)
                else:
                    records_revisions[r] = [rec]

            max_revision = max(rec.revisions)
            if max_revision > latest_record_revision:
                latest_record = rec
                latest_record_revision = max_revision
            used_revisions |= set(rec.revisions)

        # Now let's sort company records inside each revision
        for r, records in records_revisions.items():
            records_revisions[r] = sorted(
                records, key=self.key_by_company_status, reverse=True
            )

        persons_revisions = defaultdict(list)
        for p in self.persons.filter(persons_filter_clause):
            max_revision = max(p.revisions)
            for r in p.revisions:
                persons_revisions[r].append(p)

            if max_revision > latest_persons_revision:
                latest_persons = [p]
                latest_persons_revision = max_revision
            elif max_revision == latest_persons_revision:
                latest_persons.append(p)

            used_revisions |= set(p.revisions)

        def hash_for_persons(records):
            return tuple(sorted(r.person_hash for r in records))

        def hash_for_companies(records):
            return tuple(sorted(r.company_hash for r in records))

        return {
            "global_revisions": global_revisions,
            "used_revisions": sorted(used_revisions),
            "latest_record": latest_record,
            "latest_record_revision": latest_record_revision,
            "grouped_company_records": self.group_revisions(
                global_revisions,
                records_revisions,
                hash_field_getter=hash_for_companies,
            ),
            "grouped_persons_records": self.group_revisions(
                global_revisions, persons_revisions, hash_field_getter=hash_for_persons
            ),
            "latest_persons": latest_persons,
            "latest_persons_revision": latest_persons_revision,
            "records_revisions": records_revisions,
        }

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"


class CompanyRecordManager(models.Manager):
    def mass_registration_addresses(self, revision=None, cutoff=100):
        if revision is None:
            revision = Revision.objects.order_by("-created").first().pk

        qs = self.filter(revisions__contains=[revision])

        return OrderedDict(
            (rec["shortened_validated_location"], rec["addr_count"])
            for rec in qs.values("shortened_validated_location")
            .annotate(addr_count=models.Count("shortened_validated_location"))
            .filter(addr_count__gte=cutoff)
            .order_by("-addr_count")
        )


class CompanyRecord(models.Model):
    COMPANY_STATUSES = {
        0: _("інформація відсутня"),
        1: _("зареєстровано"),
        2: _("припинено"),
        3: _("в стані припинення"),
        4: _("зареєстровано, свідоцтво про державну реєстрацію недійсне"),
        5: _("порушено справу про банкрутство"),
        6: _("порушено справу про банкрутство (санація)"),
        7: _("розпорядження майном"),
        8: _("ліквідація"),
    }

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="records"
    )
    company_hash = models.CharField(
        "Ключ дедуплікації", max_length=40, primary_key=True
    )
    name = models.TextField("Назва компанії")
    short_name = models.TextField("Скорочена назва компанії", blank=True)
    location = models.TextField("Адреса реєстрації", blank=True)
    parsed_location = models.TextField("Адреса реєстрації (уніфікована)", blank=True)
    validated_location = models.TextField(
        "Адреса реєстрації (після верифікації за реєстром)", blank=True
    )
    shortened_validated_location = models.TextField(
        "Адреса реєстрації (після верифікації за реєстром та без району)",
        blank=True,
        db_index=True,
    )
    company_profile = models.TextField("Основний вид діяльності", blank=True)
    status = models.IntegerField(
        choices=COMPANY_STATUSES.items(), verbose_name="Статус компанії"
    )
    revisions = ArrayField(models.IntegerField(), default=list, verbose_name="Ревізії")

    location_postal_code = models.CharField("Індекс", max_length=40, default="")
    location_region = models.CharField("Регіон", max_length=100, default="")
    location_locality = models.CharField("Місто", max_length=100, default="")
    location_district = models.CharField("Район", max_length=100, default="")
    location_street_address = models.CharField("Вулиця/дім", max_length=200, default="")
    location_apartment = models.CharField(
        "Квартира/офіс/кімната", max_length=100, default=""
    )
    location_parsing_quality = models.FloatField("Якість парсингу адреси", default=0)

    validated_location_postal_code = models.CharField(
        "Валідований Індекс", max_length=40, default=""
    )
    validated_location_region = models.CharField(
        "Валідований Регіон", max_length=100, default=""
    )
    validated_location_locality = models.CharField(
        "Валідоване Місто", max_length=100, default=""
    )
    validated_location_district = models.CharField(
        "Валідований Район", max_length=100, default=""
    )
    validated_location_street_address = models.CharField(
        "Валідована Вулиця/дім", max_length=200, default=""
    )
    validated_location_apartment = models.CharField(
        "Валідована Квартира/офіс/кімната", max_length=100, default=""
    )

    objects = CompanyRecordManager()

    @classmethod
    def get_status(cls, status):
        for k, v in cls.COMPANY_STATUSES.items():
            if v.lower() == status.lower():
                return k
        else:
            raise StatusDoesntExist("Cannot find status {}".format(status))

    @property
    def org_form(self):
        if self.short_name.strip():
            tokenized = tokenize_words(self.short_name)
            if tokenized:
                return tokenized[0].upper()

        return "NONE"

    def get_parsed_location(self):
        return ", ".join(
            filter(
                None,
                [
                    self.location_postal_code,
                    self.location_region,
                    self.location_district,
                    self.location_locality,
                    self.location_street_address,
                    self.location_apartment,
                ],
            )
        )

    def get_validated_location(self):
        return ", ".join(
            filter(
                None,
                [
                    self.validated_location_postal_code,
                    self.validated_location_region,
                    self.validated_location_district,
                    self.validated_location_locality,
                    self.validated_location_street_address,
                    self.validated_location_apartment,
                ],
            )
        )

    def get_shortened_validated_location(self):
        return ", ".join(
            filter(
                None,
                [
                    self.validated_location_postal_code,
                    self.validated_location_region,
                    self.validated_location_street_address,
                    self.validated_location_apartment,
                ],
            )
        )

    def to_dict(self):
        dct = model_to_dict(
            self, fields=["name", "short_name", "location", "company_profile"]
        )

        dct["status"] = self.get_status_display()
        return dct

    class Meta:
        index_together = ("company", "company_hash")


class Person(models.Model):
    PERSON_TYPES = {
        "head": _("Голова"),
        "founder": _("Засновник"),
        "owner": _("Бенефіціарний власник"),
    }
    name = ArrayField(models.TextField(), default=list, verbose_name="Імена")
    person_hash = models.TextField("Ключ дедуплікації", primary_key=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Компанія",
        related_name="persons",
    )
    person_type = models.CharField(
        max_length=10, choices=PERSON_TYPES.items(), db_index=True
    )
    was_dereferenced = models.BooleanField(default=False)
    address = ArrayField(models.TextField(), default=list, verbose_name="Адреси")
    country = ArrayField(models.TextField(), default=list, verbose_name="Країни")
    raw_record = models.TextField(blank=True, verbose_name="Оригінал запису")
    tokenized_record = models.TextField(blank=True, verbose_name="Токенізований запис")
    share = models.TextField(blank=True, verbose_name="Уставний внесок")
    revisions = ArrayField(models.IntegerField(), default=list, verbose_name="Ревізії")
    bo_is_absent = models.BooleanField(
        default=False,
        verbose_name="В реєстрі було прямо вказано, що бенефіціар відсутній",
    )


class CompanySnapshotFlags(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Компанія",
        related_name="snapshot_stats",
    )

    revision = models.ForeignKey(
        Revision,
        on_delete=models.CASCADE,
        verbose_name="Ревізія",
        related_name="snapshot_stats",
    )

    charter_capital = models.FloatField(null=True, default=None)
    has_bo = models.BooleanField(default=False)
    has_bo_persons = models.BooleanField(default=False)
    has_bo_companies = models.BooleanField(default=False)
    has_dereferenced_bo = models.BooleanField(default=False)
    has_only_persons_bo = models.BooleanField(default=False)
    has_only_companies_bo = models.BooleanField(default=False)

    has_founder_persons = models.BooleanField(default=False)
    has_founder_companies = models.BooleanField(default=False)
    has_only_persons_founder = models.BooleanField(default=False)
    has_only_companies_founder = models.BooleanField(default=False)

    all_founder_persons = ArrayField(
        models.TextField(), default=list, verbose_name="Усі засновники ФО"
    )
    all_owner_persons = ArrayField(
        models.TextField(), default=list, verbose_name="Усі бенефіціарні власники ФО"
    )
    has_same_person_as_bo_and_founder = models.BooleanField(default=False)
    has_same_person_as_bo_and_head = models.BooleanField(default=False)
    has_same_person_as_head_and_founder = models.BooleanField(default=False)

    has_very_similar_person_as_bo_and_founder = models.BooleanField(default=False)
    has_very_similar_person_as_bo_and_head = models.BooleanField(default=False)
    has_very_similar_person_as_head_and_founder = models.BooleanField(default=False)

    all_similar_founders_and_bos = JSONField(
        default=list, verbose_name="Результати порівняння бенефіціарів та засновників"
    )
    all_similar_heads_and_bos = JSONField(
        default=list, verbose_name="Результати порівняння бенефіціарів та директорів"
    )
    all_similar_heads_and_founders = JSONField(
        default=list, verbose_name="Результати порівняння директорів за засновників"
    )

    all_bo_countries = ArrayField(
        models.TextField(),
        default=list,
        verbose_name="Усі країни окрім України, до яких прив'язані БО",
    )
    all_founder_countries = ArrayField(
        models.TextField(),
        default=list,
        verbose_name="Усі країни окрім України, до яких прив'язані засновники",
    )
    has_bo_on_occupied_soil = models.BooleanField(default=False)
    has_bo_in_crimea = models.BooleanField(default=False)
    acting_and_explicitly_stated_that_has_no_bo = models.BooleanField(default=False)
    not_present_in_revision = models.BooleanField(default=False)
    has_mass_registration_address = models.BooleanField(default=False)
    has_changes_in_bo = models.BooleanField(default=False)
    has_changes_in_ownership = models.BooleanField(default=False)

    bo_diff = JSONField(default=dict, verbose_name="Зміни в БО")
    ownership_diff = JSONField(default=dict, verbose_name="Зміни в власності")

    has_pep_owner = models.BooleanField(default=False)
    had_pep_owner_in_the_past = models.BooleanField(default=False)
    has_undeclared_pep_owner = models.BooleanField(default=False)
    has_discrepancy_with_declarations = models.BooleanField(default=False)
    self_owned = models.BooleanField(default=False)
    indirectly_self_owned = models.BooleanField(default=False)


class PEPOwner(models.Model):
    years = ArrayField(
        models.IntegerField(),
        default=list,
        verbose_name="Роки в котрих декларувалася інформація про БО",
    )
    person = models.CharField(max_length=100, verbose_name="Особа ПЕП")
    person_url = models.URLField(max_length=100, verbose_name="Посилання на pep.org.ua")
    from_declaration = models.BooleanField(default=False, verbose_name="Зв'язок утворений з інформації з декларації")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, verbose_name="Компанія", related_name="peps"
    )

    def __str__(self):
        return "{} є бенефіціарним власником {}".format(self.person, self.company_id)


class SelfOwned(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, verbose_name="Компанія", related_name="self_owned"
    )
    level = models.IntegerField(default=1)
