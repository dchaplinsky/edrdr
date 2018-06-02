"""
Django settings for edrdr project.

Generated by 'django-admin startproject' using Django 1.11.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'tg=jh69mhw%*rd)o93^e5d8gu6+2v!)y5dy+$o$o&qt_io*#)c'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []
LANGUAGE_CODE = 'uk'
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pipeline',

    'companies',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
    ]

    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]

    INTERNAL_IPS = ["127.0.0.1"]


ROOT_URLCONF = 'edrdr.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [os.path.join(BASE_DIR, "jinja2")],
        'APP_DIRS': True,
        'OPTIONS': {
            'environment': "jinja2_env.environment",
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            "extensions": [
                'pipeline.jinja2.PipelineExtension',
                'jinja2.ext.i18n',
                'jinja2.ext.with_'
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

PIPELINE = {
    'CSS_COMPRESSOR': 'pipeline.compressors.cssmin.CssminCompressor',
    'JS_COMPRESSOR': 'pipeline.compressors.uglifyjs.UglifyJSCompressor',
    'STYLESHEETS': {
        'css_all': {
            'source_filenames': (
                'css/screen.css',
            ),
            'output_filename': 'css/merged.css',
            'extra_context': {},
        }
    },
    'JAVASCRIPT': {
        'js_all': {
            'source_filenames': (
                "js/core/jquery.min.js",
                "js/core/bootstrap.bundle.min.js",
                "js/core/jquery.slimscroll.min.js",
                "js/core/jquery.scrollLock.min.js",
                "js/core/jquery.appear.min.js",
                "js/core/jquery.countTo.min.js",
                "js/core/js.cookie.min.js",
                "js/core/bootstrap3-typeahead.js",
                "js/bihus.js",
                "js/main.js",
                "js/common.js",
                "js/autocomplete.js",
            ),
            'output_filename': 'js/merged.js',
        }
    }
}


WSGI_APPLICATION = 'edrdr.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        # Strictly PostgreSQL
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'edrdr',
        'USER': 'edrdr',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'uk'

gettext = lambda s: s
LANGUAGES = (
    ('uk', gettext('Ukrainian')),
)


TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'

DATA_STORAGE_PATH = "/Users/dchaplinsky/Projects/edrdr/data/"

CACHEOPS_REDIS = "redis://localhost:6379/2"

CACHEOPS = {
    'companies.*': {
        'ops': 'all', 'timeout': 12 * 60 * 60
    }
}

CACHEOPS_DEGRADE_ON_FAILURE = True

PARSING_REDIS = "redis://localhost:6379/4"
PROXY = None

NUM_THREADS = 4
PATH_TO_SECRET_SAUCE = ""

# Setup Elasticsearch default connection
ELASTICSEARCH_CONNECTIONS = {
    'default': {
        'hosts': 'localhost',
        'timeout': 20
    }
}

try:
    from .local_settings import *
except ImportError:
    pass


# # Init Elasticsearch connections
from elasticsearch_dsl import connections
connections.connections.configure(**ELASTICSEARCH_CONNECTIONS)
