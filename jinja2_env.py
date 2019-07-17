from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import formats, timezone
from django.urls import reverse
from django.utils.translation import gettext, ngettext

from jinja2 import Environment

from names_translator.name_utils import title
from companies.tools.formaters import ukr_plural, curformat
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


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
    })
    env.install_gettext_callables(
        gettext=gettext, ngettext=ngettext, newstyle=True
    )

    env.filters.update({
        "datetime": lambda dt: formats.date_format(
            timezone.localtime(
                timezone.make_aware(parse_dt(dt)) if isinstance(dt, str) else dt
            ),
            "DATE_FORMAT",
        ),
        'title': title,
        'uk_plural': ukr_plural,
        'curformat': curformat,
    })
    env.globals.update({
        'updated_querystring': updated_querystring,
        'parse_and_generate': parse_and_generate
    })

    return env
