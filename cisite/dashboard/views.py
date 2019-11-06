"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define dashboard views.
"""
import copy
import json
import math
import os
from datetime import timedelta
from http import HTTPStatus
from logging import getLogger
from urllib.parse import urljoin

import requests
import requests.exceptions
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import Http404, HttpResponseRedirect, \
    HttpResponseServerError, HttpResponse, JsonResponse
from django.middleware import csrf
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import dateformat
from django.utils.dateparse import parse_datetime
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from rest_framework.authtoken.models import Token

from .pagination import _get_displayed_page_numbers, _get_page_links
from .util import api_session, build_upload_url, format_timedelta, \
    ipa_session, ParseIPAChangePassword, pw_get, get_all_pages
from .forms import EnvironmentForm
from shared.util import requests_to_response

logger = getLogger('dashboard')


def text_color_classes(bg_class):
    """Return optimal Bootstrap text and background classes for the given class.

    The colors are chosen based on the Bootstrap documentation.
    """
    foregrounds = {
        'primary': 'white',
        'secondary': 'white',
        'success': 'white',
        'danger': 'white',
        'warning': 'dark',
        'info': 'white',
        'light': 'dark',
        'dark': 'white',
        'white': 'dark',
        'transparent': 'dark',
    }
    return 'bg-{0:s} text-{1:s}'.format(
        bg_class, foregrounds.get(bg_class, 'dark'))


def parse_page(page):
    """Parse the page to a positive 0-indexed number.

    If the page number is not a number or less than 0, then it will be set to 0.
    """
    if page is None:
        page = 0
    else:
        try:
            page = int(page) - 1
        except ValueError:
            page = 0
    if page < 0:
        page = 0
    return page


def paginate_rest(page, context, count):
    """Create paginated context based on the REST API.

    Since we are using the REST API, we don't have access to the models, so we
    can't really use the built-in paginator view. However, we can utilize their
    paginator methods.

    `page` expectes to be a well formatted, zero-indexed number.
    Pass to `parse_page` before passing to `paginate_rest`.

    The `context` dictionary will get modified with the following:
    {
        next_page: page|None
        previous_page: page|None
        page_numbers: [{is_break, is_active, number}]
    }
    (This is similar to DRF pagination.py)
    """
    page += 1

    pages = int(math.ceil(count / settings.REST_FRAMEWORK['PAGE_SIZE']))

    # silently make page 0 equal to page 1
    if page == 0:
        page = 1

    # silently covert 0 pages to 1
    if pages == 0:
        pages = 1

    # depending on the page the user is on and if they switch between filters,
    # just set the current page to the max page if page > pages.
    # this avoids the assertion error thrown by _get_displayed_page_numbers.
    # the behavior follows the REST API, where instead of redirecting
    # to the last page with real results, this returns a page with an
    # empty table (since the extra offset is still sent to the REST API).
    if page > pages:
        page = pages

    page_numbers = _get_displayed_page_numbers(page, pages)
    context['pages'] = _get_page_links(page_numbers, page)

    context['next_page'] = None
    if page != pages:
        context['next_page'] = page + 1

    context['previous_page'] = None
    if page > 1:
        context['previous_page'] = page - 1


class AuthenticationForm(auth_forms.AuthenticationForm):
    """Bootstrap-themed authentication form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})


class BaseDashboardView(TemplateView):
    """Define a base view for all non-login dashboard template views."""

    # Fake cache for development. This only lasts for a single dashboard request.
    dev_cache = {}

    def add_static_context_data(self, context):
        """Add static context data included with every dashboard view.

        This is expected to not raise any exception; any exceptions raised
        here may be ignored by the caller.
        """
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
        context['enable_admin'] = settings.ENABLE_ADMIN
        context['enable_rest_api'] = settings.ENABLE_REST_API
        return context

    def get_context_data(self, **kwargs):
        """Get the static context data for all dashboard views."""
        context = super().get_context_data(**kwargs)
        return self.add_static_context_data(context)

    def get(self, *args, **kwargs):
        """Handle GET requests to the dashboard."""

        # Make sure the cache is reset, since it's used per request
        self.dev_cache = {}

        try:
            return super().get(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            logger.exception('Backend connection error')
            context = dict()
            try:
                self.add_static_context_data(context)
            except Exception:
                logger.exception('Unable to get static context data '
                                 'while rendering 503 view')
            return TemplateResponse(self.request, '503.html', context=context,
                                    status=HTTPStatus.SERVICE_UNAVAILABLE)
        finally:
            for key in self.dev_cache:
                logger.debug(f'{key}: {self.dev_cache[key]["hits"]} '
                             'cache hit(s)')
            # Save some memory
            self.dev_cache = {}

    def add_status(self, patchset, session, add_range=True, **kwargs):
        """Pass in the patchset to apply a range."""
        summary = patchset['result_summary']
        if add_range:
            summary['incomplete_range'] = range(summary['incomplete'])
        for tc_id in summary['testcases']:
            tc = summary['testcases'][tc_id]
            tc['testcase'] = self.get_cache_request(
                urljoin(settings.API_BASE_URL, f'testcases/{tc_id}/'), session)
            if add_range:
                tc['passed_range'] = range(tc['passed'])
                tc['failed_range'] = range(tc['failed'])

    def get_cache_request(self, key, session, timeout=2400):
        """Get and cache the the return the response json of a GET request.

        This is assumed to be an UNAUTHENTICATED url since it shared between
        users.

        Timeout is in seconds.

        This cache method used to only be a "request cache", where for a single
        dashboard request, it would cache API calls, then clear the cache.
        Now this is only the case in a development environment.
        This was fine for a while, but it was realized that all the requests
        used thus far has been for unauthenticated urls and there were
        essentially "cache misses" when we used javascript to load parts of the
        page. Using a session cache was also not desirable, because the
        information thus far could be shared with any users and session caches
        last too long for this use case.
        """
        if settings.ENVIRONMENT == 'development':
            if key in self.dev_cache:
                cache_item = self.dev_cache[key]
                cache_item['hits'] += 1
                val = cache_item['value']
            else:
                resp = session.get(key)
                resp.raise_for_status()
                val = resp.json()
                self.dev_cache[key] = {'hits': 0, 'value': val}
        else:
            val = cache.get(key)
            if val is None:
                logger.debug(f'{key} not in cache, setting...')
                resp = session.get(key)
                resp.raise_for_status()
                val = resp.json()
                cache.set(key, val, timeout)
        return val

    def set_cache_request(self, item, session, key, timeout=2400):
        """Set and cache the the return of a GET request.

        This uses the value of the item[key] as the key for the cache and
        replaces the value with the result of the request.

        Timeout is in seconds.

        For example:
        `item = {'branch': 'https://example.com/branch/1/'}`
        `set_cache_request(item, ..., 'branch')`
        Will transform into:
        `item = {'branch': {'name': 'abcd', 'id': 1}}`
        """
        if not item[key]:
            return
        item[key] = self.get_cache_request(item[key], session, timeout)

    def add_testcases(self, context, s):
        """Add testcases to the context"""
        url = urljoin(settings.API_BASE_URL, 'testcases/')
        context['testcases'] = get_all_pages(url, s)


class LoginView(BaseDashboardView, auth_views.LoginView):
    """Custom login view which logs the user into the REST API."""

    form_class = AuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['title'] = 'Log in'
        return context

    def form_valid(self, form):
        """Handle POST requests to the login view."""
        endresp = super().form_valid(form)

        with api_session(self.request) as s:
            login_url = urljoin(settings.API_BASE_URL, 'api-auth/login/')
            try:
                r = s.get(login_url)
                r.raise_for_status()
                r = s.post(login_url,
                           data={'username': form.cleaned_data['username'],
                                 'password': form.cleaned_data['password'],
                                 'csrfmiddlewaretoken': r.cookies['csrftoken'],
                                 'next': '/'},
                           allow_redirects=False)
                r.raise_for_status()
                self.request.session['api_sessionid'] = r.cookies['sessionid']
            except requests.exceptions.ConnectionError:
                logger.exception(
                    f'Connection closed into backend API: {login_url}')
                auth_logout(self.request)
                return HttpResponseRedirect(self.request.get_full_path())
            except requests.exceptions.HTTPError as e:
                logger.exception(
                    f'Unable to log into backend API: {e.response.text}')
                auth_logout(self.request)
                return HttpResponseServerError(
                    content='<p>Unable to login to backend API</p>')

        # Check to see if they can directly use IPA. If not, redirect
        # them to change their password.
        if 'django_auth_ldap.backend.LDAPBackend' in \
                settings.AUTHENTICATION_BACKENDS:
            with ipa_session(form.cleaned_data['username'],
                             form.cleaned_data['password']) as \
                    (session, resp, ipa_url):
                if not resp.ok:
                    messages.warning(self.request,
                                     "Your password has expired, "
                                     "please change your password.")
                    return HttpResponseRedirect(reverse('password_change'))
        return endresp


class PatchSet(BaseDashboardView):
    def set_patchset_submitter(self, series):
        """Returns the patchset submitter as it should be output.

        The output will be just the name for an anonymous user or the name
        plus e-mail for a logged in user. This should prevent spambots from
        harvesting e-mails off of our dashboard.
        """
        submitter = series['submitter']
        ret = submitter.get('name') or '(unknown)'
        request = self.request
        if request.user.is_authenticated and submitter.get('email'):
            ret += ' <' + submitter['email'] + '>'
        series['submitter'] = ret

    def patchwork_range_str(self, series):
        """Return the range of patchwork IDs as an HTML string."""
        res = str(series['patches'][0]['id'])
        if len(series['patches']) > 1:
            res += f'–{series["patches"][-1]["id"]}'
        return res

    def set_shown_patchset(self, context):
        """Sets the shown context and returns whether to show active ps."""
        shown = self.request.GET.get('patchsets', 'active')
        context['shown'] = {}
        if shown == 'all':
            context['shown']['text'] = 'all'
            context['shown']['all'] = True
            return ''
        elif shown == 'inactive':
            context['shown']['text'] = 'inactive'
            context['shown']['inactive'] = True
            return False
        # 'active' and fallback, set active to True
        context['shown']['text'] = 'active'
        context['shown']['active'] = True
        return True

    def update_patchsets(self, context, session, **kwargs):
        with requests.Session() as pw_session:
            for patchset in context['patchsets']:
                series = pw_get(patchset['pw_series_url'], pw_session)
                if not series['name']:
                    series['name'] = f'Untitled series #{series["id"]}'
                patchset['series'] = series
                patchset['patchwork_range_str'] = \
                    self.patchwork_range_str(series)
                self.set_patchset_submitter(series)
                if 'time_to_last_test' in patchset:
                    patchset['time_to_last_test'] = format_timedelta(
                        timedelta(
                            seconds=float(patchset['time_to_last_test'])))
                self.add_status(patchset, session, **kwargs)
                patchset['detail_url'] = reverse(
                    'patchset_detail', args=(patchset['id'],))


class PatchSetList(PatchSet):
    """Display the list of patches on the dashboard."""

    template_name = 'patchset_list.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Patch sets'
        active = self.set_shown_patchset(context)

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            offset = page * settings.REST_FRAMEWORK['PAGE_SIZE']
            resp = s.get(urljoin(settings.API_BASE_URL, 'patchsets/'), params={
                'pw_is_active': active,
                'without_series': False,
                'ordering': '-id',
                'offset': offset,
                'limit': 1,
                'cache': True,
            })
            resp.raise_for_status()
            resp_json = resp.json()
            end = min(offset + settings.REST_FRAMEWORK['PAGE_SIZE'], resp_json['count'])
            context['patchsets'] = resp_json['results']
            context['start'] = offset
            context['end'] = end
            # Limit chosen based on speed when cached (overall page load) and
            # speed when uncached (overall page load AND first row response)
            context['limit'] = 4
            context['range'] = range(offset, end)
            paginate_rest(page, context, resp_json['count'])

        self.update_patchsets(context, s)
        return context


class PatchSetRow(PatchSet):
    """Display the list of patches on the dashboard."""

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
        active = self.set_shown_patchset(context)

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            resp = s.get(urljoin(settings.API_BASE_URL, 'patchsets/'), params={
                'pw_is_active': active,
                'without_series': False,
                'ordering': '-id',
                'offset': page * settings.REST_FRAMEWORK['PAGE_SIZE'] + self.kwargs["offset"],
                'limit': self.request.GET.get('limit') or 1,
                'cache': True,
            })
            resp.raise_for_status()
            resp_json = resp.json()
            context['patchsets'] = resp_json['results']

            self.update_patchsets(context, s, **kwargs)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(add_range=False, **kwargs)

        # Remove not needed things from patchset -- saves some bandwidth
        for ps in context['patchsets']:
            ps['series'].pop('project', None)
            ps['series'].pop('patches', None)
            ps['series'].pop('cover_letter', None)

        return JsonResponse({
            'patchsets': context['patchsets'],
            'request': {
                'user': {
                    'is_superuser': request.user.is_superuser
                }
            }
        })


class Tarball(BaseDashboardView):
    def show_elements(self, s, owner):
        # if the user is not in the owning group, then don't show
        # certain elements, such as links (since they won't have access
        # anyways)
        group = self.get_cache_request(owner, s)
        user = self.request.user
        return user.groups.filter(name=group['name']).exists() or user.is_staff

    def populate_envs(self, s, runs):
        """
        Update environment dict based on the environments in the runs
        """
        # Populate active environments
        api_resp = s.get(urljoin(settings.API_BASE_URL, 'environments/'),
                         params={'active': True})
        if api_resp.status_code in [HTTPStatus.UNAUTHORIZED,
                                    HTTPStatus.FORBIDDEN]:
            envs = {}
        else:
            api_resp.raise_for_status()
            envs = api_resp.json()['results']
            envs = {x['url']: x for x in envs}

        # Populate inactive environments from old runs
        for run_url, run in runs.items():
            env = run['environment']
            show_elements = self.show_elements(s, env['owner'])

            # hide download artifact button to invalid users
            if not run['public_download'] and not show_elements:
                run['log_upload_file'] = None

            if show_elements:
                # check if user has owner group to show visibility button
                run['is_owner'] = True

            envs[env['url']] = env

        # Update environment data
        for env_url, env in envs.items():
            if env.get('live_since'):
                env['live_since'] = parse_datetime(env['live_since'])

            # parse the absolute url to our proxied url
            if env.get('hardware_description'):
                env['hardware_description'] = build_upload_url(
                    self.request, env['hardware_description'])

            # hide rerun button to invalid users
            if not self.show_elements(s, env['owner']):
                env['pipeline'] = None

        return envs

    def populate_runs(self, s, run_urls):
        """
        Return populated runs list along with an environment

        The environment needs to be updated after this is called.
        """
        runs = {}

        for run_url in run_urls:
            resp = s.get(run_url)
            if resp.status_code >= HTTPStatus.BAD_REQUEST:
                continue
            run = resp.json()

            self.set_cache_request(run, s, 'branch')

            if run['log_upload_file']:
                run['log_upload_file'] = build_upload_url(
                    self.request, run['log_upload_file'])

            run['timestamp'] = parse_datetime(run['timestamp'])
            run['failure_count'] = 0

            for result in run['results']:
                self.set_parameter_keys(result['measurement'])
                if result['result'] == 'FAIL':
                    run['failure_count'] += 1

            run['environment'] = s.get(run['environment']).json()
            # hide download artifact button to invalid users
            if (not run['public_download'] and
                    not self.show_elements(s, run['environment']['owner'])):
                run['log_upload_file'] = None

            runs[run_url] = run

        return runs

    def populate_test_cases(self, s, runs):
        # Legacy test case results check. Set test case to test run.
        for run_url, run in runs.items():
            if run['testcase']:
                continue
            if run['results']:
                # If the test run does not have a test case, check its results.
                # Assume that there is only one testcase per run
                measurement = run['results'][0]['measurement']
                run['testcase'] = measurement['testcase']
            elif run['log_upload_file']:
                # If there are no results, then it means there was a test
                # harness error. Unfortunately, there is no test case attached
                # to a test run, only to test results. This may get resolved
                # when Bug 254 is resolved (since a test case would be attached
                # to a test run)
                run['testcase'] = 'other'

        # for each test case, add all runs
        test_cases = {}

        for run_url, run in runs.items():
            if not run['testcase']:
                continue

            tc = run['testcase']
            if tc not in test_cases:
                test_cases[tc] = {}
                if tc == 'other':
                    test_cases[tc]['testcase'] = {'name': 'other'}
                else:
                    test_cases[tc]['testcase'] = s.get(tc).json()
                test_cases[tc]['runs'] = []

            test_cases[tc]['runs'].append(run)

            # Needed for reruns
            run['testcase'] = test_cases[tc]['testcase']

        return test_cases

    def populate_tarball_context(self, context, s):
        if context['tarball'].get('date'):
            context['tarball']['date'] = parse_datetime(context['tarball']['date'])

        self.set_cache_request(context['tarball'], s, 'branch')
        self.set_ci_download_url(context['tarball'])

        runs = self.populate_runs(s, context['tarball']['runs'])
        envs = self.populate_envs(s, runs)
        test_cases = self.populate_test_cases(s, runs)

        # Order by envs { testcases { runs { results }}}
        for env_url, env in envs.items():
            env['testcases'] = {}

            for tc_url, tc in test_cases.items():
                runs = []
                for run in tc['runs']:
                    if env['id'] == run['environment']['id']:
                        runs.append(run)

                # only add test cases if runs exist
                if not runs:
                    continue

                # reverse the runs so that the latest run is first
                runs = list(reversed(runs))
                # deepcopy, so that the reference is not the same between
                # environments
                env['testcases'][tc_url] = copy.deepcopy(tc['testcase'])
                env['testcases'][tc_url]['runs'] = runs

                self.set_all_pass(env, runs)

        # Finally, update the context
        context['environments'] = envs

    def set_all_pass(self, env, runs):
        """Check to see if a non-pass exists."""
        if 'all_pass' not in env:
            # set default to incomplete
            env['all_pass'] = None
        elif env['all_pass'] is False:
            # if a previous test case failed, then skip checking other test cases
            return

        # if no runs, then keep as incomplete
        if not runs:
            return

        latest_run = runs[0]
        if not latest_run['results']:
            # a test run with no results is an indeterminate result
            env['all_pass'] = False
            return

        # since there are runs, just set to pass, and check if fail
        env['all_pass'] = True
        for result in latest_run['results']:
            if result['result'] != 'PASS':
                env['all_pass'] = False
                break

    def set_parameter_keys(self, measurement):
        """Update the parameter list to be an object with name as the key.

        This is to force proper "ordering" of the parameters. One day,
        the measurements page or serializer should be updated to do this
        instead of the dashboard. However, that is difficult. See DPDKLAB-386.
        """
        if not measurement:
            return

        new_parameters = {}
        for parameter in measurement['parameters']:
            # can't use special characters in django templates...
            new_parameters[parameter['name'].replace('/', '_')] = parameter
        measurement['parameters'] = new_parameters

    def set_ci_download_url(self, tarball):
        """Returns a url based on the id and filename.

        Even though a filename is not necessary, it looks more natural on the client.
        """
        # hopefully the API never returns parameters
        tarball['tarball_name'] = os.path.basename(tarball['tarball_url'])
        args = [tarball['id'], tarball['tarball_name']]
        tarball['tarball_url'] = self.request.build_absolute_uri(
            reverse('tarball-download', args=args))

    def set_shown_tarball(self, context):
        """Sets the shown context and returns whether to show active ps."""
        shown = self.request.GET.get('tarballs', 'without')
        context['shown'] = {}
        if shown == 'all':
            context['shown']['text'] = 'all'
            context['shown']['all'] = True
            return ''
        elif shown == 'with':
            context['shown']['text'] = 'with associated patch set'
            context['shown']['with'] = True
            return True
        # 'without' and fallback, set withot to True
        context['shown']['text'] = 'without associated patch set'
        context['shown']['without'] = True
        return False

    def update_tarballs(self, context, s, **kwargs):
        for tarball in context['tarballs']:
            self.set_cache_request(tarball, s, 'branch')
            self.add_status(tarball, s, **kwargs)

            if tarball['date']:
                tarball['date'] = dateformat.format(
                    parse_datetime(tarball['date']),
                    settings.DATETIME_FORMAT)

            if tarball['patchset']:
                resp = s.get(tarball['patchset'])
                resp.raise_for_status()
                tarball['patchset'] = resp.json()
                tarball['patchset']['detail_url'] = reverse(
                    'patchset_detail', args=(tarball['patchset']['id'],))

            tarball['detail_url'] = reverse(
                'tarball_detail', args=(tarball['id'],))


class PatchSetDetail(Tarball, PatchSet):
    """Display the details for a particular patchset on the dashboard."""

    template_name = 'patchset_detail.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     f'patchsets/{self.kwargs["id"]}/'))
            if api_resp.status_code == HTTPStatus.NOT_FOUND:
                raise Http404
            context['patchset'] = api_resp.json()
            # since we now rely on series information, raise a 404 if there is
            # no series attached
            if not context['patchset']['series_id']:
                raise Http404

            self.add_testcases(context, s)

            series = pw_get(context['patchset']['pw_series_url'])
            context['patchset']['series'] = series
            context['patchset']['patchwork_range_str'] = \
                self.patchwork_range_str(series)
            self.add_status(context['patchset'], s)
            # assume UTC
            context['patchset']['date'] = parse_datetime(f'{series["date"]}+00:00')
            self.set_patchset_submitter(series)

            context['environments'] = dict()
            if context['patchset'].get('tarballs', []):
                context['tarball'] = s.get(context['patchset']['tarballs'][-1]).json()
                self.populate_tarball_context(context, s)

            elif context['patchset']['build_log']:
                api_resp = s.get(context['patchset']['build_log'])
                if api_resp.status_code == 404:
                    log = ('A "404 Not Found" was returned from the CI. The CI '
                           'may be down or the build was deleted.')
                else:
                    api_resp.raise_for_status()
                    log = api_resp.text
                context['patchset']['build_log'] = log
                # normally gathered from tarball, but since there is none,
                # grab branch from patchset
                self.set_cache_request(context['patchset'], s, 'branch')

            # Used for rebuilds
            if self.request.user.is_authenticated:
                api_resp = s.get(urljoin(settings.API_BASE_URL, f'branches/'))
                api_resp.raise_for_status()
                context['branches'] = api_resp.json()['results']

        context['title'] = f'Patch set {context["patchset"]["id"]}'
        context['status_classes'] = text_color_classes(context['patchset']['status_class'])
        return context


class TarballList(Tarball):
    """Display the list of master comparisons on the dashboard."""

    template_name = 'tarball_list.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Tarballs'

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            offset = page * settings.REST_FRAMEWORK['PAGE_SIZE']
            without = self.set_shown_tarball(context)

            resp = s.get(urljoin(settings.API_BASE_URL, 'tarballs/'), params={
                'has_patchset': without,
                'ordering': '-date',
                'offset': offset,
                'limit': 1,
                'cache': True,
            })

            resp.raise_for_status()
            resp_json = resp.json()

            end = min(offset + settings.REST_FRAMEWORK['PAGE_SIZE'], resp_json['count'])
            context['tarballs'] = resp_json['results']
            context['start'] = offset
            context['end'] = end
            # Limit chosen based on speed when cached (overall page load) and
            # speed when uncached (overall page load AND first row response)
            context['limit'] = 4
            context['range'] = range(offset, end)
            paginate_rest(page, context, resp_json['count'])

        self.update_tarballs(context, s)
        return context


class TarballRow(Tarball):
    """Display the list of patches on the dashboard."""

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            without = self.set_shown_tarball(context)

            resp = s.get(urljoin(settings.API_BASE_URL, 'tarballs/'), params={
                'has_patchset': without,
                'without_series': False,
                'ordering': '-date',
                'offset': page * settings.REST_FRAMEWORK['PAGE_SIZE'] + self.kwargs["offset"],
                'limit': self.request.GET.get('limit') or 1,
                'cache': True,
            })
            resp.raise_for_status()
            resp_json = resp.json()
            context['tarballs'] = resp_json['results']

            self.update_tarballs(context, s, **kwargs)
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(add_range=False, **kwargs)

        return JsonResponse({
            'tarballs': context['tarballs'],
            'request': {
                'user': {
                    'is_superuser': request.user.is_superuser
                }
            }
        })


class TarballDetail(Tarball):
    """Display the details for a particular patchset on the dashboard."""

    template_name = 'tarball_detail.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the tarball for the test runs."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     f'tarballs/{self.kwargs["id"]}/'))
            if api_resp.status_code == HTTPStatus.NOT_FOUND:
                raise Http404
            context['tarball'] = api_resp.json()
            self.add_status(context['tarball'], s)

            self.add_testcases(context, s)

            self.populate_tarball_context(context, s)

            if context['tarball']['patchset']:
                resp = s.get(context['tarball']['patchset'])
                resp.raise_for_status()
                context['tarball']['patchset'] = resp.json()

        context['title'] = f'Tarball {context["tarball"]["id"]}'
        context['status_classes'] = text_color_classes(context['tarball']['status_class'])
        return context


class BasePreferencesView(LoginRequiredMixin, BaseDashboardView):
    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        # Set next to homepage in case of logout, so that it doesn't just
        # redirect to the login page
        context['next'] = reverse('dashboard')
        context['enable_rest_api'] = settings.ENABLE_REST_API

        user = self.request.user
        # check if the user is a primary contact for any of their groups
        for group in user.groups.all():
            if user.has_perm('manage_group', group.results_vendor):
                context['primary_contact'] = True
                break

        return context


class Preferences(BasePreferencesView):
    """Show user preferences."""

    def get(self, *args, **kwargs):
        """Redirect the user to the subscriptions page for now."""
        return HttpResponseRedirect(reverse('subscriptions'))


class Subscriptions(BasePreferencesView):
    """Show subscription preferences.

    DELETE, PATCH, and POST are proxy subscription calls to REST API.
    """

    template_name = 'preferences/subscriptions.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Subscriptions'
        return context

    def get(self, request, *args, **kwargs):
        # can be an empty string
        if request.GET.get('json', None) is None:
            return super().get(request, *args, **kwargs)

        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     'subscriptions/?mine=true'))
            api_resp.raise_for_status()
            subscriptions = api_resp.json()
            api_resp = s.get(
                urljoin(settings.API_BASE_URL, 'environments/'),
                params={'active': True, 'mine': True})
            environments = api_resp.json()

        # [{"environment": Foo, "subscription": None}]
        env_sub_pairs = []

        for env in environments['results']:
            # Remove not needed things -- saves some bandwidth
            env.pop('measurements', None)

            # grab first subscription that contains the current environment
            sub = next(filter(lambda sub: sub['environment'] == env['url'],
                              subscriptions['results']), None)
            # sub gets set to None if a subscription for the environment does
            # not exist
            env_sub_pairs.append({'environment': env, 'subscription': sub})

        return JsonResponse({
            'env_sub_pairs': env_sub_pairs,
            'csrftoken': csrf.get_token(request)
        })

    def post(self, request, *args, **kwargs):
        """Pass post request to REST API."""
        with api_session(request) as s:
            url = urljoin(settings.API_BASE_URL, 'subscriptions/')
            response = s.post(url, data=json.loads(request.body))
            # default response does not contain a GET
            return JsonResponse(response.json(), status=response.status_code)

    def delete(self, request, subscription, *args, **kwargs):
        """Pass delete request to REST API."""
        with api_session(request) as s:
            url = urljoin(settings.API_BASE_URL, f'subscriptions/{subscription}/')
            response = s.delete(url)
            # default response does not contain a GET
            return HttpResponse(status=response.status_code)

    def patch(self, request, subscription, *args, **kwargs):
        """Pass patch request to REST API."""
        with api_session(request) as s:
            url = urljoin(settings.API_BASE_URL, f'subscriptions/{subscription}/')
            response = s.patch(url, data=json.loads(request.body))
            # default response does not contain a GET
            return JsonResponse(response.json(), status=response.status_code)


class PasswordChangeForm(auth_forms.PasswordChangeForm):
    """Password change form with IPA and bootstrap integration."""

    def __init__(self, *args, **kwargs):
        """Bootstrap-themed password change form."""
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})

    def clean_old_password(self):
        """Verify password differently when using ldap for authentication.

        If LDAP authentication is used, then skip the current password
        validation, and pass it to IPA when trying to actually change the
        password from within the View.
        """
        if 'django_auth_ldap.backend.LDAPBackend' in\
                settings.AUTHENTICATION_BACKENDS:
            return self.cleaned_data['old_password']
        else:
            return super().clean_old_password()


class PasswordChangeView(BasePreferencesView, auth_views.PasswordChangeView):
    """Change password view."""

    form_class = PasswordChangeForm

    def form_valid(self, form):
        """Handle changing password through IPA.

        Also force a login to refresh the API session. (by removing the
        `update_session_auth_hash` method that is in super())
        """
        if 'django_auth_ldap.backend.LDAPBackend' in\
                settings.AUTHENTICATION_BACKENDS:
            data = {
                'user': self.request.user.username,
                'old_password': form.cleaned_data['old_password'],
                'new_password': form.cleaned_data['new_password1']
            }
            resp = requests.post(urljoin(settings.IPA_URL,
                                         'session/change_password'),
                                 data=data,
                                 verify=settings.CA_CERT_BUNDLE,
                                 headers={'referer': settings.IPA_URL})
            parser = ParseIPAChangePassword()
            parser.feed(resp.text)
            if parser.header == 'Password change successful':
                return HttpResponseRedirect(self.get_success_url())
            else:
                # The username should always be correct in this case since the
                # user is already logged in at this point.
                if parser.message ==\
                        'The old password or username is not correct.':
                    messages.error(self.request,
                                   'The old password is not correct.')
                else:
                    messages.error(self.request,
                                   f'{parser.header}: {parser.message}')
                return HttpResponseRedirect(reverse('password_change'))
        else:
            form.save()
        return super(auth_views.PasswordChangeView, self).form_valid(form)


class PasswordChangeDoneView(BasePreferencesView, auth_views.PasswordChangeDoneView):
    """Inherit BaseDashboardView for context."""


class RESTAPIPreferences(BasePreferencesView):
    """Show REST API preferences."""

    template_name = 'preferences/rest_api_preferences.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        token = Token.objects.filter(user=self.request.user).first()
        if token:
            context['api_token_created'] = token.created
        context['api_url'] = settings.API_BASE_URL
        context['title'] = 'REST API Preferences'
        return context

    def get(self, *args, **kwargs):
        """Raise 404 if rest api is not enabled."""
        if not settings.ENABLE_REST_API:
            raise Http404

        return super().get(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Generate or Regenerate a new API key"""
        if not settings.ENABLE_REST_API:
            raise Http404

        Token.objects.filter(user=self.request.user).delete()
        Token.objects.create(user=self.request.user)

        token = Token.objects.filter(user=self.request.user).first()
        messages.add_message(request, messages.INFO, f'Your API Token: {token}')
        return HttpResponseRedirect(reverse('rest_api_preferences'))


class AboutView(BaseDashboardView):
    """Display the about page."""

    template_name = 'about.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'About'

        with api_session(self.request) as s:
            resp = s.get(urljoin(settings.API_BASE_URL, 'statuses/'))
            resp.raise_for_status()
            context['statuses'] = resp.json()['results']

            self.add_testcases(context, s)

        return context


class UploadView(View):
    """Proxy media storage calls."""

    def get(self, request, path):
        """Proxy media storage get request.

        `path` is the relative path to the media (does not include
        PRIVATE_STORAGE_URL). This then gets appended to
        API_BASE_URL + PRIVATE_STORAGE_URL.
        """
        with api_session(self.request) as s:
            url = urljoin(settings.API_BASE_URL,
                          settings.PRIVATE_STORAGE_URL[1:] + path)
            r = s.get(url)
            return requests_to_response(r)


class CIDownloadView(View):
    """Proxy CI downloads."""

    def get(self, request, pk, filename):
        """Get from API

        Filename parameter, although not used, is used to allow client URL to
        have an arbitrary filename, which looks better to the client.
        """
        with api_session(self.request) as s:
            r = s.get(urljoin(settings.API_BASE_URL,
                              f'tarballs/{pk}/download/'))
        return requests_to_response(r)


class Rerun(LoginRequiredMixin, View):
    """Proxy a rerun to the results view."""

    def post(self, request, tr_id, *args, **kwargs):
        with api_session(self.request) as s:
            api_resp = s.post(urljoin(settings.API_BASE_URL,
                                      f'testruns/{tr_id}/rerun/'))
            api_resp.raise_for_status()
            messages.success(request,
                             'The test is now rerunning. Please check back '
                             'in at least 10 minutes for an updated result.')
        next_url = request.GET.get('next')
        if next_url:
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect(reverse('dashboard'))


class StatsView(BaseDashboardView):
    """Display the graph page."""

    template_name = 'stats.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Stats'
        context['grafana_url'] = settings.GRAFANA_URL
        context['grafana_graphs'] = settings.GRAFANA_GRAPHS
        return context


class Rebuild(LoginRequiredMixin, View):
    """Proxy a rebuild to the results view."""

    def post(self, request, ps_id, *args, **kwargs):
        with api_session(self.request) as s:
            branch = request.POST.get('branch')
            api_resp = s.post(urljoin(settings.API_BASE_URL,
                                      f'patchsets/{ps_id}/rebuild/{branch}/'))
            api_resp.raise_for_status()
            messages.success(request,
                             f'The patchset is now rebuilding on {branch}. '
                             'Please check back in at least 10 minutes for an '
                             'updated result.')
        next_url = request.GET.get('next')
        if next_url:
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect(reverse('dashboard'))


class Build(LoginRequiredMixin, View):
    """Proxy a build to the results view."""

    def post(self, request, tb_id, *args, **kwargs):
        with api_session(self.request) as s:
            pipeline = request.POST.get('pipeline')
            api_resp = s.post(urljoin(settings.API_BASE_URL,
                                      f'tarballs/{tb_id}/build/{pipeline}/'))
        if api_resp.status_code == 404:
            messages.error(request, f'{pipeline} does not exist.')
        else:
            api_resp.raise_for_status()
            messages.success(request,
                             f'The tarball is now building on {pipeline}. '
                             'Please check back in at least 10 minutes '
                             'for an updated result.')
        next_url = request.GET.get('next')
        if next_url:
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect(reverse('dashboard'))


class CIStatusView(BaseDashboardView):
    """Display the CI status page."""

    template_name = 'status.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Status'

        with api_session(self.request) as s:
            context['jobs_url'] = reverse('ci_jobs')

            # ci status
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'ci-status/'))
            status = api_resp.json()['results']
            context['status'] = status

            # ci nodes
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'ci-nodes/'))
            nodes = api_resp.json()['results']
            context['nodes'] = nodes

            # ci build queue
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'ci-queue/'))
            queue = api_resp.json()['results']
            context['queue'] = queue

        return context


class ManageUsers(BasePreferencesView):
    """Manage users page."""

    template_name = 'preferences/manage_users.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'users/'), params={
                'managed': True
            })
            api_resp.raise_for_status()
            managed_users = api_resp.json()

            user = self.request.user
            # get all groups the user is a primary contact
            managed_groups = []
            for group in self.request.user.groups.all():
                if user.has_perm('manage_group', group.results_vendor):
                    managed_groups.append(group.name)

            # create a dictionary of managed_group[user]
            # since the user could be a primary contact for multiple groups and
            # users could also be in multiple groups
            group_to_user = {}
            for managed_group in managed_groups:
                group_to_user[managed_group] = []
                for managed_user in managed_users['results']:
                    for user_group in managed_user['groups']:
                        name = self.get_cache_request(user_group, s)['name']
                        if name == managed_group:
                            group_to_user[managed_group].append(managed_user)

        context['group_users'] = group_to_user
        context['title'] = 'Manage Users'
        return context


class ManageUsersRemove(LoginRequiredMixin, View):
    """Proxy a delete to the results view."""

    def post(self, request, user, group, *args, **kwargs):
        with api_session(request) as s:
            response = s.delete(
                urljoin(settings.API_BASE_URL,
                        f'users/{user}/group/{group}/'))
            response.raise_for_status()
        messages.success(
            request, f'{user} has been removed from the group {group}.')
        return HttpResponseRedirect(reverse('manage_users'))


class ManageUsersAdd(LoginRequiredMixin, View):
    """Proxy a post to the results view."""

    def post(self, request, group, *args, **kwargs):
        user = request.POST.get('user')
        with api_session(request) as s:
            response = s.post(
                urljoin(settings.API_BASE_URL,
                        f'users/{user}/group/{group}/'))

        if response.status_code == 404:
            messages.error(request, f'{user} does not exist.')
        else:
            response.raise_for_status()
            messages.success(
                request, f'{user} has been added to the group {group}.')

        return HttpResponseRedirect(reverse('manage_users'))


class ManageEnvironments(FormView, BasePreferencesView):
    """Manage environments page."""

    template_name = 'preferences/manage_environments.html'
    form_class = EnvironmentForm
    success_url = '.'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)

        with api_session(self.request) as s:
            api_resp = s.get(
                urljoin(settings.API_BASE_URL, 'environments/'),
                params={'active': True, 'mine': True})

        environments = api_resp.json()['results']

        for env in environments:
            if env['live_since']:
                # only show date from the datetime, so it can be rendered in
                # the html input properly
                env['live_since'] = env['live_since'].split('T')[0]

            if env['hardware_description']:
                env['hardware_description'] = build_upload_url(
                    self.request, env['hardware_description'])

        context['environments'] = environments
        context['title'] = 'Manage Environments'
        return context

    def form_valid(self, form):
        nic_make = form.cleaned_data['nic_make']
        nic_model = form.cleaned_data['nic_model']
        live_since = form.cleaned_data['live_since']
        env = form.cleaned_data['environment']
        hw_description = form.cleaned_data['hardware_description']

        if live_since:
            live_since = live_since.strftime("%Y-%m-%dT%H:%M:%SZ")

        send = {
            'nic_make': nic_make,
            'nic_model': nic_model,
            'live_since': live_since,
        }
        files = {}

        if hw_description:
            files['hardware_description'] = hw_description

        with api_session(self.request) as s:
            api_resp = s.patch(
                urljoin(settings.API_BASE_URL, f'environments/{env}/'),
                json=send, files=files)

        if api_resp.status_code != requests.codes.ok:
            messages.error(self.request, api_resp.text)
            return super().form_valid(form)

        messages.success(self.request, 'Saved successfully!')
        return super().form_valid(form)


class TogglePublic(LoginRequiredMixin, View):
    """Toggle a given testrun's download link publicity."""

    def post(self, request, tr_id, *args, **kwargs):
        with api_session(self.request) as s:
            api_resp = s.post(urljoin(settings.API_BASE_URL,
                                      f'testruns/{tr_id}/toggle_public/'))
            api_resp.raise_for_status()
            # since true gives 1 when indexing, can use this
            status = ['private', 'public'][api_resp.json()['public_download']]
            messages.success(request, f'Download is now {status}')
        next_url = request.GET.get('next')
        if next_url:
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect(reverse('dashboard'))


class CIJobs(BaseDashboardView):
    """Proxy CI Jobs page"""

    def get(self, request, id=None, **kwargs):
        url = urljoin(settings.API_BASE_URL, f'ci-jobs/')
        # in case of id 0
        if id is not None:
            url += f'{id}/'

        resp = cache.get(url)

        if resp is None:
            with api_session(request) as s:
                resp = s.get(url)

            resp_json = resp.json()
            status_code = resp.status_code

            # Arbitrarily cache the job(s) for 10 minutes
            cache.set(url, {
                'json': resp_json,
                'status_code': status_code
            }, 10 * 60)
        else:
            resp_json = resp['json']
            status_code = resp['status_code']

        # handle list of jobs vs single jobs
        if id is None:
            jobs = resp_json['results']
            for job in jobs:
                self.set_job(job)
            return JsonResponse(jobs, status=status_code, safe=False)

        self.set_job(resp_json)

        # update time (only in detail view)
        ms = resp_json['estimatedDuration']
        sec = (ms / 1000) % 60
        sec = int(sec)
        min = (ms / (1000 * 60)) % 60
        min = int(min)
        hour = int(ms / (1000 * 60 * 60))

        ftime = ''
        if hour > 1:
            ftime = f'{hour} hr '
        ftime += f'{min} min {sec} sec'
        resp_json['estimatedDuration'] = ftime

        return JsonResponse(resp_json, status=status_code)

    def set_job(self, job):
        # update url to dashboard url
        job['url'] = reverse('ci_jobs', args=(job['id'],))
