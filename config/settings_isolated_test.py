"""
Test settings that can only reach a disposable PostgreSQL server.

The database is never taken from DJANGO_DB_* or .env. It must be named with KASRA_TEST_DB_*
variables, and config.test_runner refuses to create the test database unless the server reports
DISPOSABLE_CLUSTER_NAME and the role is not a superuser.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F401,F403

DISPOSABLE_CLUSTER_NAME = 'kasra_p0_2_disposable'
FORBIDDEN_TEST_DB_HOSTS = {'db', 'books-db-1', 'localhost', '127.0.0.1', '::1', 'host.docker.internal'}


def _required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} must be set to run tests against the disposable database.')
    return value


_host = _required('KASRA_TEST_DB_HOST')
if _host.lower() in FORBIDDEN_TEST_DB_HOSTS:
    raise ImproperlyConfigured(f'KASRA_TEST_DB_HOST={_host} is a development host, not the disposable server.')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': _required('KASRA_TEST_DB_USER'),
        'PASSWORD': _required('KASRA_TEST_DB_PASSWORD'),
        'HOST': _host,
        'PORT': int(os.environ.get('KASRA_TEST_DB_PORT', '5432')),
        'TEST': {'NAME': 'test_kasra_p0_2'},
    }
}

TEST_RUNNER = 'config.test_runner.DisposableDatabaseTestRunner'
SMS_ENABLED = False
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
