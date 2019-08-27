# CI Website for DPDK Community Lab

This is a Django-based website and API for the DPDK performance test lab.

## Local Installation

Python3.6+ is required.

You will need to install `apache2-dev`, `libmysqlclient-dev`, and `pipenv`.

Try using the `./configure` script to create the environment.

Now, just run `pipenv shell` whenever you want
to work on this Django project.

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

* `JENKINS_URL`: The Jenkins URL to allow for rerunning tests from the
  dashboard.

* `JENKINS_USER`: The Jenkins API user for rerunning tests from the
  dashboard.

* `JENKINS_API_TOKEN`: The Jenkins API token of the JENKINS_USER for rerunning
   tests from the dashboard.

* `GRAFANA_URL`: The Grafana URL. This is used in the stats page and can be
  used for `GRAFANA_GRAPHS` below.

* `GRAFANA_GRAPHS`: A list of urls from grafana to to display. For example:
  `GRAFANA_GRAPHS = [GRAFANA_URL + 'd/qao3xzbmz/master-comparison']`

## Jenkins assumptions

Currently, we use Jenkins as the CI. As such, there are a few assumptions that
the API expects.

Reruns are based on the environment pipeline name and the test case pipeline
name, separated by a dash.

Building a patchset is currently hardcoded to a job named Apply-Custom-Patch-Set.
This is used for rebuilding a patchset onto a different branch.

The CI job status API expects a Jenkins view called "Dashboard" to exist.

The CI nodes API expects each Jenkins computer to have the label "public" if they
are to be displayed.

## Admin page changes

Several actions have been added to the admin page to manage permissions.

### Environment

* **Set public**: Set the environment permissions allowable by the public.
This makes it so users can view the environment in the detailed pages.
This also applies the same permissions to predecessors, measurements,
test runs, and results.
If the test case used in the test runs of the environment has public download
permissions, all future artifacts will be public. There is also an option to
make the existing artifacts downloadable by the public.

* **Set private**: Set the environment permissions private.
This makes it so that the environment no longer shows up in the detailed pages.
This also applies the same permissions to predecessors, measurements,
test runs, and results.
This will make it so that future artifacts are also private. There is also an
option to make the existing artifacts private.

Environments are private by default.

### Test cases

* **Set public**: Set the test case artifact download permissions allowable by
the public.
If the future test runs are publicly viewable, the artifacts will be public.
There is also an option to make the existing artifacts downloadable by the
public.

* **Set private**: Set the test case artifact download permissions private.
This will make it so that future artifacts are also private. There is also an
option to make the existing artifacts private.

Test case artifact downloads are private by default.

## Running the server

```
$ cd cisite
$ python manage.py migrate
$ npm run build # used to transpile js for ie11 support
$ python manage.py livereload --host 0 # optional: refresh pages on file changes
$ python manage.py runserver 0:8000
```

Use the last argument to be able to access the server from another
system; omit it if you only need to access from localhost.

If doing Javascript development, it will be helpful to have the scripts auto transpile with:
```
$ npm run dev
```

## Testing

```sh
./manage.py test --settings cisite.settings_test
```

## Docker

If you prefer to use Docker instead, run the commands below:

### Development with Docker

```sh
docker-compose up dev_migrate
docker-compose up dev # Only specific folders are used as volumes. See docker-compose.yml for more info.
```

### Testing with Docker

```sh
docker-compose up test_migrate
docker-compose up test_style
docker-compose up test
```

### Production with Docker

```sh
docker-compose up build
# WIP: Run with local Apache/SQL/Memcached
```
