from django.db import models
from django.utils.translation import ugettext_noop as _
from django.contrib.postgres.fields import ArrayField
from companies.exceptions import StatusDoesntExist


class Revision(models.Model):
    revision_id = models.IntegerField("Номер ревізії", primary_key=True)
    dataset_id = models.TextField("Датасет")
    created = models.DateTimeField("Дата створення")
    imported = models.BooleanField("Імпорт завершено", default=False)
    url = models.URLField("Посилання на набір данних")


class Company(models.Model):
    edrpou = models.IntegerField(primary_key=True)

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

    @classmethod
    def get_status(cls, status):
        for k, v in cls.COMPANY_STATUSES.items():
            if v.lower() == status.lower():
                return k
        else:
            raise StatusDoesntExist("Cannot find status {}".format(status))

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
