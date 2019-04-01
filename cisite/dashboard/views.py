"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define dashboard views.
"""

from datetime import timedelta
from logging import getLogger
from http import HTTPStatus
from urllib.parse import urljoin
import requests
import requests.exceptions
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout as auth_logout
from django.views.generic import TemplateView, View
from django.http import Http404, HttpResponseRedirect, \
    HttpResponseServerError, HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.dateparse import parse_datetime
import json
import math
import os

from .pagination import _get_displayed_page_numbers, _get_page_links
from .util import api_session, build_upload_url, format_timedelta, \
    ipa_session, ParseIPAChangePassword, pw_get
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


class LoginView(auth_views.LoginView):
    """Custom login view which logs the user into the REST API."""

    form_class = AuthenticationForm

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
        if 'django_auth_ldap.backend.LDAPBackend' in\
                settings.AUTHENTICATION_BACKENDS:
            with ipa_session(form.cleaned_data['username'],
                             form.cleaned_data['password']) as\
                    (session, resp, ipa_url):
                if not resp.ok:
                    messages.warning(self.request,
                                     "Your password has expired, "
                                     "please change your password.")
                    return HttpResponseRedirect(reverse('password_change'))
        return endresp


class BaseDashboardView(TemplateView):
    """Define a base view for all non-login dashboard template views."""

    # cache branches
    branches = {}

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

    def add_status_ranges(self, patchset):
        """Pass in the patchset to apply a range."""
        patchset['incomplete_range'] = range(patchset['incomplete'])
        patchset['passed_range'] = range(patchset['passed'])
        patchset['failed_range'] = range(patchset['failed'])

    def set_branch(self, item, session):
        """Set and cache branch on object."""
        if not item['branch']:
            return
        if item['branch'] in self.branches:
            branch = self.branches[item['branch']]
        else:
            resp = session.get(item['branch'])
            resp.raise_for_status()
            branch = resp.json()
            self.branches[item['branch']] = branch
        item['branch'] = branch


class PatchSet(BaseDashboardView):
    def get_patchset_submitter(self, series):
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
        return ret

    def patchwork_range_str(self, series):
        """Return the range of patchwork IDs as an HTML string."""
        res = str(series['patches'][0]['id'])
        if len(series['patches']) > 1:
            res += f'&ndash;{series["patches"][-1]["id"]}'
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

    def update_patchsets(self, context):
        with requests.Session() as pw_session:
            for patchset in context['patchsets']:
                series = pw_get(patchset['pw_series_url'], pw_session)
                if not series['name']:
                    series['name'] = f'Untitled series #{series["id"]}'
                patchset['series'] = series
                patchset['patchwork_range_str'] = \
                    self.patchwork_range_str(series)
                patchset['submitter'] = self.get_patchset_submitter(series)
                if 'time_to_last_test' in patchset:
                    patchset['time_to_last_test'] = format_timedelta(
                        timedelta(
                            seconds=float(patchset['time_to_last_test'])))
                self.add_status_ranges(patchset)


class PatchSetList(PatchSet):
    """Display the list of patches on the dashboard."""

    template_name = 'patchset_list.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
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

        self.update_patchsets(context)
        return context


class PatchSetRow(PatchSet):
    """Display the list of patches on the dashboard."""

    template_name = 'patchset_row.html'

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

        self.update_patchsets(context)
        return context


class Tarball(BaseDashboardView):
    def populate_tarball_context(self, context, s, envs):
        if context['tarball'].get('date'):
            context['tarball']['date'] = parse_datetime(context['tarball']['date'])

        self.set_branch(context['tarball'], s)
        self.set_ci_download_url(context['tarball'])
        context['environments'] = {x: None for x in envs}

        for url in context['tarball']['runs']:
            resp = s.get(url)
            if resp.status_code >= HTTPStatus.BAD_REQUEST:
                continue

            run = resp.json()
            self.set_branch(run, s)

            if run['log_upload_file']:
                run['log_upload_file'] = build_upload_url(
                    self.request, run['log_upload_file'])

            run['timestamp'] = parse_datetime(run['timestamp'])
            run['failure_count'] = 0
            run['testcases'] = {}

            for result in run['results']:
                resp = s.get(result['measurement'])
                # in case the user does not have permission
                if resp.status_code >= HTTPStatus.BAD_REQUEST:
                    continue

                measurement = resp.json()
                self.set_parameter_keys(measurement)
                result['measurement'] = measurement
                if result['result'].upper() == 'FAIL':
                    run['failure_count'] += 1

                tc = result['measurement']['testcase']
                if not run['testcases'].get(tc):
                    run['testcases'][tc] = s.get(tc).json()
                    run['testcases'][tc]['results'] = []

                run['testcases'][tc]['results'].append(result)

            # Get the latest version of the environment, since previous
            # versions won't show up in the list of active environments
            # that we obtained above
            env_url = run['environment']
            resp = s.get(env_url)
            # in case the user does not have permission
            if resp.status_code >= HTTPStatus.BAD_REQUEST:
                continue

            env = resp.json()

            while (env_url not in context['environments'].keys() and
                   env.get('successor')):
                env_url = env['successor']
                env = s.get(env_url).json()

            if env.get('live_since'):
                env['live_since'] = parse_datetime(env['live_since'])

            # parse the absolute url to our proxied url
            if env.get('hardware_description'):
                env['hardware_description'] = build_upload_url(
                    self.request, env['hardware_description'])

            # if the user is not in the owning group, then don't show
            # certain elements, such as links (since they won't have access
            # anyways)
            group = s.get(env['owner']).json()
            user = self.request.user
            show_elements = (user.groups.filter(name=group['name']).exists() or
                             user.is_staff)

            # avoid duplicate replacements since we try to get the
            # latest environment multiple times inside the test run
            # loop
            if not context['environments'][env_url]:
                env['runs'] = []
                # hide rerun button to invalid users
                if not show_elements:
                    env['pipeline_url'] = None
                context['environments'][env_url] = env

            # hide download artifact button to invalid users
            if not show_elements:
                run['log_upload_file'] = None

            context['environments'][env_url]['runs'].append(run)

    def set_parameter_keys(self, measurement):
        """Update the parameter list to be an object with name as the key.

        This is to force proper "ordering" of the parameters. One day,
        the measurements page or serializer should be updated to do this
        instead of the dashboard. However, that is difficult. See DPDKLAB-386.
        """
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

            series = pw_get(context['patchset']['pw_series_url'])
            context['patchset']['patches'] = series['patches']
            context['patchset']['patchwork_range_str'] = \
                self.patchwork_range_str(series)
            self.add_status_ranges(context['patchset'])
            # assume UTC
            context['patchset']['date'] = parse_datetime(f'{series["date"]}+00:00')
            context['patchset']['submitter'] = self.get_patchset_submitter(series)
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'environments/'),
                             params={'active': True})
            if api_resp.status_code in [HTTPStatus.UNAUTHORIZED,
                                        HTTPStatus.FORBIDDEN]:
                envs = dict()
            else:
                api_resp.raise_for_status()
                envs = api_resp.json()['results']
                envs = {x['url']: x for x in envs}

            context['environments'] = dict()
            if context['patchset'].get('tarballs', []):
                context['tarball'] = s.get(context['patchset']['tarballs'][-1]).json()
                self.populate_tarball_context(context, s, envs)

            elif context['patchset']['build_log']:
                api_resp = s.get(context['patchset']['build_log'])
                api_resp.raise_for_status()
                context['patchset']['build_log'] = api_resp.text
                self.set_branch(context['patchset'], s)

            if context['patchset']['has_error']:
                api_resp = s.get(urljoin(settings.API_BASE_URL, f'branches/'))
                api_resp.raise_for_status()
                context['branches'] = api_resp.json()['results']

            for env_url, env in context['environments'].items():
                # Fill in details of missing environments so they can be
                # displayed in the template
                if env is None:
                    context['environments'][env_url] = envs[env_url]
                elif 'runs' in context['environments'][env_url]:
                    # also reverse the runs so that the latest run is first
                    context['environments'][env_url]['runs'] = \
                        list(reversed(context['environments'][env_url]['runs']))

            context['status_classes'] = text_color_classes(context['patchset']['status_class'])
            return context


class TarballList(Tarball):
    """Display the list of master comparisons on the dashboard."""

    template_name = 'tarball_list.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            offset = page * settings.REST_FRAMEWORK['PAGE_SIZE']
            without = self.set_shown_tarball(context)

            resp = s.get(urljoin(settings.API_BASE_URL, 'tarballs/'), params={
                'has_patchset': without,
                'ordering': '-date',
                'offset': offset,
            })

            resp.raise_for_status()
            resp_json = resp.json()

            context['tarballs'] = resp_json['results']
            for tarball in context['tarballs']:
                self.set_branch(tarball, s)
                self.add_status_ranges(tarball)

                if tarball['date']:
                    tarball['date'] = parse_datetime(tarball['date'])

                if tarball['patchset']:
                    resp = s.get(tarball['patchset'])
                    resp.raise_for_status()
                    tarball['patchset'] = resp.json()

            paginate_rest(page, context, resp_json['count'])

        return context


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
            self.add_status_ranges(context['tarball'])
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'environments/'),
                             params={'active': True})
            if api_resp.status_code in [HTTPStatus.UNAUTHORIZED,
                                        HTTPStatus.FORBIDDEN]:
                envs = dict()
            else:
                api_resp.raise_for_status()
                envs = api_resp.json()['results']
                envs = {x['url']: x for x in envs}

            context['environments'] = dict()

            self.populate_tarball_context(context, s, envs)

            if context['tarball']['patchset']:
                resp = s.get(context['tarball']['patchset'])
                resp.raise_for_status()
                context['tarball']['patchset'] = resp.json()

            for env_url, env in context['environments'].items():
                # Fill in details of missing environments so they can be
                # displayed in the template
                if env is None:
                    context['environments'][env_url] = envs[env_url]
                elif 'runs' in context['environments'][env_url]:
                    # also reverse the runs so that the latest run is first
                    context['environments'][env_url]['runs'] = \
                        list(reversed(context['environments'][env_url]['runs']))

            context['status_classes'] = text_color_classes(context['tarball']['status_class'])
            return context


class Preferences(LoginRequiredMixin, View):
    """Show user preferences."""

    def get(self, *args, **kwargs):
        """Redirect the user to the subscriptions page for now."""
        return HttpResponseRedirect(reverse('subscriptions'))


class NextToHomeMixin():
    """Set the next context to the homepage.

    This is used when, for example, logging out of a page that normally
    requires a login, such as the prefrences page.
    """

    def get_context_data(self, **kwargs):
        """Set the next context to the homepage."""
        context = super().get_context_data(**kwargs)
        context['next'] = reverse('dashboard')
        return context


class Subscriptions(LoginRequiredMixin, NextToHomeMixin, BaseDashboardView):
    """Show subscription preferences.

    DELETE, PATCH, and POST are proxy subscription calls to REST API.
    """

    template_name = 'subscriptions.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     'subscriptions/?mine=true'))
            api_resp.raise_for_status()
            subscriptions = api_resp.json()
            api_resp = s.get(
                urljoin(settings.API_BASE_URL, 'environments/'),
                params={'active': True})
            environments = api_resp.json()

        # [{"environment": Foo, "subscription": None}]
        env_sub_pairs = []

        for env in environments['results']:
            # grab first subscription that contains the current environment
            sub = next(filter(lambda sub: sub['environment'] == env['url'],
                              subscriptions['results']), None)
            # sub gets set to None if a subscription for the environment does
            # not exist
            env_sub_pairs.append({'environment': env, 'subscription': sub})

        context['env_sub_pairs'] = env_sub_pairs
        context['title'] = 'Subscriptions'
        return context

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


class PasswordChangeView(BaseDashboardView, NextToHomeMixin, auth_views.PasswordChangeView):
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


class PasswordChangeDoneView(BaseDashboardView, NextToHomeMixin, auth_views.PasswordChangeDoneView):
    """Inherit BaseDashboardView for context."""


class AboutView(BaseDashboardView):
    """Display the about page."""

    template_name = 'about.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)

        with api_session(self.request) as s:
            resp = s.get(urljoin(settings.API_BASE_URL, 'statuses/'))
            resp.raise_for_status()
            context['statuses'] = resp.json()['results']

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
