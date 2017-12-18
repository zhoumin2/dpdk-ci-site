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
```

Now, just run `. ~/.venv/dpdklab-cisite/bin/activate` whenever you want
to work on this Django project. Run `deactivate` to leave the virtual
environment (which will remove django-admin, flake8, etc. from your path
and you will then be on the default Python version for your OS).

## Running the server

```
$ cd cisite
$ python manage.py migrate
$ python manage.py runserver 0:8000
```

Use the last argument to be able to access the server from another
system; omit it if you only need to access from localhost.
