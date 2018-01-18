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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
