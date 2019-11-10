from datetime import date
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import formats, timezone
from django.urls import reverse
from django.utils.translation import gettext, ngettext

from jinja2 import Environment

from names_translator.name_utils import title
from companies.tools.formaters import ukr_plural, curformat
from companies.tools.phones import format_phone, truncate_phone
from names_translator.name_utils import parse_and_generate


def updated_querystring(request, params):
    """Updates current querystring with a given dict of params, removing
    existing occurrences of such params. Returns a urlencoded querystring."""
    original_params = request.GET.copy()
    for key in params:
        if key in original_params:
            original_params.pop(key)
    original_params.update(params)
    return original_params.urlencode()


def ensure_aware(dt):
    if timezone.is_aware(dt):
        return dt
    else:
        return timezone.make_aware(dt)


def datetime_filter(dt, dayfirst=False):
    return (
        formats.date_format(
            timezone.localtime(
                ensure_aware(
                    parse_dt(dt, dayfirst=dayfirst) if isinstance(dt, str) else dt
                )
            ),
            "DATE_FORMAT",
        )
        if dt
        else ""
    )


def date_filter(dt, dayfirst=False):
    if isinstance(dt, date):
        return formats.date_format(dt, "DATE_FORMAT")

    return (
        formats.date_format(
            timezone.localtime(
                ensure_aware(
                    parse_dt(dt, dayfirst=dayfirst) if isinstance(dt, str) else dt
                )
            ),
            "DATE_FORMAT",
        )
        if dt
        else ""
    )


def environment(**options):
    env = Environment(**options)
    env.globals.update({"static": staticfiles_storage.url, "url": reverse})
    env.install_gettext_callables(gettext=gettext, ngettext=ngettext, newstyle=True)

    env.filters.update(
        {
            "datetime": datetime_filter,
            "date": date_filter,
            "title": title,
            "uk_plural": ukr_plural,
            "curformat": curformat,
            "format_phone": format_phone,
            "truncate_phone": truncate_phone,
        }
    )
    env.globals.update(
        {
            "updated_querystring": updated_querystring,
            "parse_and_generate": parse_and_generate,
        }
    )

    return env
