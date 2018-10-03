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
    },
    'public': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'public.sqlite3'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

STATIC_URL = '/static/'
PRIVATE_STORAGE_ROOT = 'uploads/'
PRIVATE_STORAGE_URL = '/uploads/'
MEDIA_ROOT = 'uploads/public/'
MEDIA_URL = '/uploads-public/'

REST_FRAMEWORK['PAGE_SIZE'] = 100

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend'
)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        # Looks like: [12/Apr/2018 14:44:42] results.permissions INFO mymessage
        # This is similar to django's log formatting
        'simple': {
            'format': '[%(asctime)s] %(name)s %(levelname)s %(message)s',
            'datefmt': '%d/%b/%Y %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'results': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
            'formatter': 'simple',
        },
        'dashboard': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'DEBUG'),
            'formatter': 'simple',
        },
        'javascript_error': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    },
}

#DASHBOARD_BANNER = {
#    'bg_class': 'warning',
#    'text': 'hello world'
#}

ENVIRONMENT = 'development'
API_BASE_URL = 'http://localhost:8000'
