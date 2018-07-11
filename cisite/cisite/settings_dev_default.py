"""Default settings for development systems.

This should be copied to settings.py in your local development trees.

DO NOT USE THIS FILE IN PRODUCTION!!!!
"""

from .settings_base import *

DEBUG = True
# !!!!Do NOT use this SECRET_KEY in production!!!!
SECRET_KEY = r'UNSAFEwcHpD2C5vIkYP9Wx6mMkiUKjyHyR4Jwd3GbXFug3UNSAFE'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

STATIC_URL = '/static/'

REST_FRAMEWORK['PAGE_SIZE'] = 100

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend'
)

#DASHBOARD_BANNER = {
#    'bg_class': 'warning',
#    'text': 'hello world'
#}

API_BASE_URL = 'http://localhost:8000'
