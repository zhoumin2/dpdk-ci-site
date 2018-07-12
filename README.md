# Internal Website for DPDK Performance Test Lab

This is a Django-based website and API for the DPDK performance test lab.

## Local Installation

Setting up a Python virtual environment for CentOS 7 (you can adapt
for more modern distros by just installing Python 3.6 and then running
venv/virtualenv directly):

```
$ sudo yum -y install centos-release-scl
$ sudo yum -y install rh-python36
$ scl enable python36 -- python3.6 -m venv ~/.venvs/dpdklab-cisite
$ . ~/.venvs/dpdklab-cisite/bin/activate
(cisite) $ pip install -r requirements/local.txt
...
Successfully installed Django-2.0 django-filter-1.1.0 djangorestframework-3.7.3 flake8-3.5.0 flake8-docstrings-1.1.0 flake8-polyfill-1.0.1 markdown-2.6.10 mccabe-0.6.1 pycodestyle-2.3.1 pydocstyle-2.1.1 pyflakes-1.6.0 pytz-2017.3 six-1.11.0 snowballstemmer-1.2.1
(cisite) $ pre-commit install --hook-type pre-commit
(cisite) $ pre-commit install --hook-type commit-msg
```

Now, just run `. ~/.venv/dpdklab-cisite/bin/activate` whenever you want
to work on this Django project. Run `deactivate` to leave the virtual
environment (which will remove django-admin, flake8, etc. from your path
and you will then be on the default Python version for your OS).

Note that the pre-commit hooks will fail if you attempt to commit
without activating the virtual environment first, since it looks for
`python3.6` in `$PATH`.

## Settings

* `API_BASE_URL`: The URL of the root of the REST API to be used by the
  dashboard.

* `CA_CERT_BUNDLE`: File containing PEM-encoded CA certificates to be used
  by the requests library for authenticating the REST API and other HTTPS
  sites that may be accessed by this site.

* `DASHBOARD_BANNER`: If present, expected to be a dictionary containing two
  elements: `bg_class` is the Bootstrap background color class for the banner
  at the top of the page, and `text` is the text to include in the banner.
  This banner is intended to be used for site-wide announcements.

* `ENABLE_REST_API`: If False, remove the URL routes for the REST API,
  making it unusable.

* `ENABLE_ADMIN`: If False, remove the URL route for the Django admin Web
  interface.

* `IPA_URL`: If IPA LDAP authentication is used, then while changing the
  password, it will use this url to change the password via IPA's REST API.
  `CA_CERT_BUNDLE` also needs to be set.

## Running the server

```
$ cd cisite
$ python manage.py migrate
$ python manage.py runserver 0:8000
```

Use the last argument to be able to access the server from another
system; omit it if you only need to access from localhost.
