from django.db import models
from django.utils.translation import ugettext_noop as _
from django.contrib.postgres.fields import ArrayField
from django.urls import reverse
from django.forms.models import model_to_dict

from tokenize_uk import tokenize_words
from translitua import translit, UkrainianKMU

from companies.exceptions import StatusDoesntExist
from companies.tools.names import TRANSLITERATOR, parse_fullname, title


class Revision(models.Model):
    revision_id = models.IntegerField("Номер ревізії", primary_key=True)
    dataset_id = models.TextField("Датасет")
    created = models.DateTimeField("Дата створення")
    imported = models.BooleanField("Імпорт завершено", default=False)
    ignore = models.BooleanField("Ігнорувати через помилки імпорту", default=False)
    url = models.URLField("Посилання на набір данних")

    def get_absolute_url(self):
        return reverse('revision>detail', kwargs={'pk': self.pk})


class Company(models.Model):
    edrpou = models.IntegerField(primary_key=True)

    @property
    def full_edrpou(self):
        return str(self.pk).rjust(8, "0")

    def get_absolute_url(self):
        return reverse('company>detail', kwargs={'pk': self.full_edrpou})

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
        for company_record in self.records.all():
            addresses.add(company_record.location)
            addresses.add(company_record.parsed_location)
            addresses.add(company_record.validated_location)

            company_profiles.add(company_record.company_profile)
            companies.add(company_record.name)
            companies.add(company_record.short_name)
            if max(company_record.revisions) > latest_revision:
                latest_record = company_record
                latest_revision = max(company_record.revisions)

        for person in self.persons.all():
            for name in person.name:
                persons.add(
                    (name, person.get_person_type_display())
                )

                for addr in person.address:
                    addresses.add(addr)

                for country in person.country:
                    addresses.add(country)

                raw_records.add(person.raw_record)

        for name, position in persons:
            names_autocomplete.add(title(name))
            names_autocomplete.add(translit(title(name), UkrainianKMU))

            all_persons.add("{}, {}".format(name, position))

            l, f, p, _ = parse_fullname(name)
            for tr_name in TRANSLITERATOR.transliterate(l, f, p):
                all_persons.add("{}, {}".format(tr_name, position))

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

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"


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

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="records")
    company_hash = models.CharField("Ключ дедуплікації", max_length=40, primary_key=True)
    name = models.TextField("Назва компанії")
    short_name = models.TextField("Скорочена назва компанії", blank=True)
    location = models.TextField("Адреса реєстрації", blank=True)
    company_profile = models.TextField("Основний вид діяльності", blank=True)
    status = models.IntegerField(choices=COMPANY_STATUSES.items(), verbose_name="Статус компанії")
    revisions = ArrayField(models.IntegerField(), default=list, verbose_name="Ревізії")

    location_postal_code = models.CharField("Індекс", max_length=40, default="")
    location_region = models.CharField("Регіон", max_length=100, default="")
    location_locality = models.CharField("Місто", max_length=100, default="")
    location_district = models.CharField("Район", max_length=100, default="")
    location_street_address = models.CharField("Вулиця/дім", max_length=200, default="")
    location_apartment = models.CharField("Квартира/офіс/кімната", max_length=100, default="")
    location_parsing_quality = models.FloatField("Якість парсингу адреси", default=0)

    validated_location_postal_code = models.CharField("Валідований Індекс", max_length=40, default="")
    validated_location_region = models.CharField("Валідований Регіон", max_length=100, default="")
    validated_location_locality = models.CharField("Валідоване Місто", max_length=100, default="")
    validated_location_district = models.CharField("Валідований Район", max_length=100, default="")
    validated_location_street_address = models.CharField("Валідована Вулиця/дім", max_length=200, default="")
    validated_location_apartment = models.CharField("Валідована Квартира/офіс/кімната", max_length=100, default="")

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

    @property
    def parsed_location(self):
        return ", ".join(
            filter(None, [
                self.location_postal_code,
                self.location_region,
                self.location_district,
                self.location_locality,
                self.location_street_address,
                self.location_apartment
            ])
        )

    @property
    def validated_location(self):
        return ", ".join(
            filter(None, [
                self.validated_location_postal_code,
                self.validated_location_region,
                self.validated_location_district,
                self.validated_location_locality,
                self.validated_location_street_address,
                self.validated_location_apartment
            ])
        )

    def to_dict(self):
        dct = model_to_dict(self, fields=[
            "name",
            "short_name",
            "location",
            "company_profile",
        ])

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
    name = ArrayField(models.TextField(), default=[], verbose_name="Імена")
    person_hash = models.TextField(
        "Ключ дедуплікації", primary_key=True,
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name="Компанія",
                                related_name="persons")
    person_type = models.CharField(max_length=10, choices=PERSON_TYPES.items())
    address = ArrayField(models.TextField(), default=[], verbose_name="Адреси")
    country = ArrayField(models.TextField(), default=[], verbose_name="Країни")
    raw_record = models.TextField(blank=True, verbose_name="Оригінал запису")
    tokenized_record = models.TextField(blank=True, verbose_name="Токенізований запис")
    share = models.TextField(blank=True, verbose_name="Уставний внесок")
    revisions = ArrayField(models.IntegerField(), default=list, verbose_name="Ревізії")
