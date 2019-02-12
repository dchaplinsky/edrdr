"""
Django settings for edrdr project.

Generated by 'django-admin startproject' using Django 1.11.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os
import raven

def get_env_str(k, default):
    return os.environ.get(k, default)

def get_env_str_list(k, default=""):
    if os.environ.get(k) is not None:
        return os.environ.get(k).strip().split(" ")
    return default

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_str('SECRET_KEY', 'tg=jh69mhw%*rd)o93^e5d8gu6+2v!)y5dy+$o$o&qt_io*#)c')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = get_env_str_list('ALLOWED_HOSTS', [])
LANGUAGE_CODE = 'uk'
SITE_ID = 1
SITE_URL = "https://ring.org.ua"

FORCE_SCRIPT_NAME = get_env_str('FORCE_SCRIPT_NAME', '')

STATIC_URL = get_env_str('STATIC_URL', '{}/static/'.format(FORCE_SCRIPT_NAME))
STATIC_ROOT = get_env_str('STATIC_ROOT', os.path.join(BASE_DIR, "static"))

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'qartez',
    'pipeline',
    'cacheops',
    'companies',
    'raven.contrib.django.raven_compat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
                'companies.context_processors.settings_processor',
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
                'companies.context_processors.settings_processor',
            ],
        },
    },
]

STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.CachedFileFinder',
    'pipeline.finders.PipelineFinder',
)

PIPELINE = {
    'COMPILERS': ('pipeline.compilers.sass.SASSCompiler',),
    'SASS_ARGUMENTS': '-q',
    'CSS_COMPRESSOR': 'pipeline.compressors.cssmin.CssminCompressor',
    'JS_COMPRESSOR': 'pipeline.compressors.uglifyjs.UglifyJSCompressor',
    'STYLESHEETS': {
        'css_all': {
            'source_filenames': (
                'scss/main.scss',
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
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': get_env_str('DB_NAME', 'edrdr'),
        'USER': get_env_str('DB_USER', 'edrdr'),
        'PASSWORD': get_env_str('DB_PASS', ''),
        'HOST': get_env_str('DB_HOST', '127.0.0.1'),
        'PORT': get_env_str('DB_PORT', '5432')
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

DATA_STORAGE_PATH = get_env_str('DATA_STORAGE_PATH', "/Users/dchaplinsky/Projects/edrdr/data/")

CACHEOPS_REDIS = "redis://localhost:6379/2"

CACHEOPS = {
    'companies.*': {
        'ops': 'all', 'timeout': 12 * 60 * 60
    }
}

CACHEOPS_DEGRADE_ON_FAILURE = True

PARSING_REDIS = "redis://localhost:6379/4"
PROXY = get_env_str('PROXY', None)

NUM_THREADS = int(get_env_str('NUM_THREADS', '4'))

PATH_TO_SECRET_SAUCE = get_env_str('PATH_TO_SECRET_SAUCE', "")
CATALOG_PER_PAGE = 24

# Setup Elasticsearch default connection
ELASTICSEARCH_CONNECTIONS = {
    'default': {
        'hosts': get_env_str('ELASTICSEARCH_DSN', 'localhost:9200'),
        'timeout': int(get_env_str('ELASTICSEARCH_TIMEOUT', '120'))
    }
}

try:
    GIT_VERSION = raven.fetch_git_sha(os.path.abspath(BASE_DIR))
except raven.exceptions.InvalidGitRepository:
    GIT_VERSION = "undef"
    pass

RAVEN_CONFIG = {
    'dsn': get_env_str('SENTRY_DSN', None),
    'release': get_env_str('VERSION', GIT_VERSION),
}

try:
    from .local_settings import *
except ImportError:
    pass


# # Init Elasticsearch connections
from elasticsearch_dsl import connections
connections.connections.configure(**ELASTICSEARCH_CONNECTIONS)
