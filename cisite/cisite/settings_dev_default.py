"""Default settings for development systems.

This should be copied to settings.py in your local development trees.

DO NOT USE THIS FILE IN PRODUCTION!!!!
"""

from .settings_base import *

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

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

# Regular debug apps
INSTALLED_APPS += [
]

# Apps needed before static files
INSTALLED_APPS = [
    'livereload',
] + INSTALLED_APPS

MIDDLEWARE += [
    'livereload.middleware.LiveReloadScript',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

STATIC_URL = '/static/'
STATIC_ROOT = 'static/'
PRIVATE_STORAGE_ROOT = 'uploads/'
PRIVATE_STORAGE_URL = '/uploads/'
MEDIA_ROOT = 'uploads/public/'
MEDIA_URL = '/uploads-public/'

REST_FRAMEWORK['PAGE_SIZE'] = 10

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
# Uncomment this if trying to debug database queries or to help trace where
# queries occur to try to opimize them. Keep in mind that this contains a lot
# of output and may affect performance.
#        'django.db.backends': {
#            'handlers': ['console'],
#            'level': 'DEBUG',
#        },
    },
}

#DASHBOARD_BANNER = {
#    'bg_class': 'warning',
#    'text_class': 'dark',
#    'text': 'hello world'
#}

ENVIRONMENT = 'development'
API_BASE_URL = 'http://localhost:8000'
