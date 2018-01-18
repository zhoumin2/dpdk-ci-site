#!/bin/sh
# Runs Django unit tests on CI site repository
# Expected to run from repository root directory

# Activate virtualenv
. venv/bin/activate

# Change into Django project directory
cd cisite

export DJANGO_SETTINGS_MODULE=cisite.settings_test

# TODO: Remove makemigrations after DPDKLAB-120 is resolved
python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py test --noinput \
	--testrunner="xmlrunner.extra.djangotestrunner.XMLTestRunner"
