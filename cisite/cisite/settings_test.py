#!/usr/bin/env python
# Django settings for automatic test suite runs

from .settings_base import *

DEBUG = True
# !!!!Do NOT use this SECRET_KEY in production!!!!
SECRET_KEY = r'UNSAFEwcHpD2C5vIkYP9Wx6mMkiUKjyHyR4Jwd3GbXFug3UNSAFE'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'sqlite3.db',
    }
}

REST_FRAMEWORK['PAGE_SIZE'] = 2

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

STATIC_URL = '/static/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend'
)

# This must be true for the relevant tests to pass
# It cannot be overridden per-test because the urlconf is only processed
# once as part of Django initialization.
ENABLE_PREFERENCES = True
