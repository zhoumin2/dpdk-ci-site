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
STATIC_ROOT = 'static/'
PRIVATE_STORAGE_URL = '/uploads/'
PRIVATE_STORAGE_ROOT = 'uploads/'
MEDIA_ROOT = 'uploads/public/'
MEDIA_URL = '/uploads-public/'

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend'
)

# Required to be defined for get_object() on the UserViewSet
AUTH_LDAP_USER_DN_TEMPLATE = ""

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

API_BASE_URL = 'http://example.com/'
CA_CERT_BUNDLE = None
JENKINS_URL = 'http://example.com/'
JENKINS_USER = 'none'
JENKINS_API_TOKEN = 'none'
