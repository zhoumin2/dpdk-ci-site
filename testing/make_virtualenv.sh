#!/bin/sh
# Create virtualenv for CI site requirements
# Requires python 3.6 (with -dev/-devel package) and openldap-devel

/opt/rh/rh-python36/root/usr/bin/python3.6 -m venv venv
. venv/bin/activate
pip install -r requirements/local.txt
