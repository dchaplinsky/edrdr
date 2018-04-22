from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import formats
from django.urls import reverse

from jinja2 import Environment


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
    })

    env.filters.update({
        'datetime': lambda dt: formats.date_format(dt, "DATETIME_FORMAT"),
    })
    return env
