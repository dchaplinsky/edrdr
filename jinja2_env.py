from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import formats
from django.urls import reverse
from django.utils.translation import gettext, ngettext

from jinja2 import Environment

from companies.tools.names import title
from companies.tools.formaters import ukr_plural, curformat


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
        'datetime': lambda dt: formats.date_format(dt, "DATETIME_FORMAT"),
        'title': title,
        'uk_plural': ukr_plural,
        'curformat': curformat
    })
    return env
