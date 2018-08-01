"""Define dashboard views."""

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

from .pagination import _get_displayed_page_numbers, _get_page_links
from .util import api_session, build_upload_url, format_timedelta, \
    ipa_session, ParseIPAChangePassword


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
    """Parse the page to a 0-indexed number."""
    if page is None:
        page = 0
    else:
        try:
            page = int(page) - 1
        except ValueError:
            # fail silently, since this should not happen under normal
            # conditions
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
        next: url|None
        previous: url|None
        page_links: [{is_break, is_active, url, page}]
    }
    """
    page += 1

    pages = int(math.ceil(count / getattr(settings, 'REST_FRAMEWORK')['PAGE_SIZE']))

    # silently make page 0 equal to page 1
    if page == 0:
        page = 1

    # silently covert 0 pages to 1
    if pages == 0:
        pages = 1

    # page wrapping
    if page < 0:
        page %= pages
        page += 1

    # _get_displayed_page_numbers() throws an assertion error, so just throw a
    # 404 ourselves
    if page > pages:
        raise Http404

    page_numbers = _get_displayed_page_numbers(page, pages)
    context['page_links'] = _get_page_links(
        page_numbers, page, lambda num: f'?page={num}')

    context['next'] = None
    if page != pages:
        context['next'] = f'?page={page + 1}'

    context['previous'] = None
    if page > 1:
        context['previous'] = f'?page={page - 1}'


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
            except requests.exceptions.ConnectionError as e:
                getLogger('dashboard').exception(
                    'Connection closed into backend API: %s', login_url)
                auth_logout(self.request)
                return HttpResponseRedirect(self.request.get_full_path())
            except requests.exceptions.HTTPError as e:
                getLogger('dashboard').exception('Unable to log into backend API: %s',
                                                 e.response.text)
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

    def get_patchset_submitter(self, ps):
        """Returns the patchset submitter as it should be output.

        The output will be just the name for an anonymous user or the name
        plus e-mail for a logged in user. This should prevent spambots from
        harvesting e-mails off of our dashboard.
        """
        ret = ps.get('submitter_name') or '(unknown)'
        request = self.request
        if request.user.is_authenticated and ps.get('submitter_email'):
            ret += ' <' + ps['submitter_email'] + '>'
        return ret

    def add_static_context_data(self, context):
        """Add static context data included with every dashboard view.

        This is expected to not raise any exception; any exceptions raised
        here may be ignored by the caller.
        """
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
        context['enable_preferences'] = getattr(settings, 'ENABLE_PREFERENCES', True)
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
            getLogger('dashboard').exception(
                'Backend connection error')
            context = dict()
            try:
                self.add_static_context_data(context)
            except Exception:
                getLogger('dashboard').exception(
                    'Unable to get static context data '
                    'while rendering 503 view')
            return TemplateResponse(self.request, '503.html', context=context,
                                    status=HTTPStatus.SERVICE_UNAVAILABLE)


class PatchSetList(BaseDashboardView):
    """Display the list of patches on the dashboard."""

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)

        with api_session(self.request) as s:
            page = parse_page(self.request.GET.get('page'))
            resp = s.get(urljoin(
                settings.API_BASE_URL,
                'patchsets?complete=true&ordering=-id&offset={}'
                .format(page *
                        getattr(settings, 'REST_FRAMEWORK')['PAGE_SIZE'])))
            resp.raise_for_status()
            resp_json = resp.json()
            context['patchsets'] = resp_json['results']
            paginate_rest(page, context, resp_json['count'])
            resp = s.get(urljoin(settings.API_BASE_URL,
                                 'statuses'))
            resp.raise_for_status()
            context['statuses'] = resp.json()['results']

        for ps in context['patchsets']:
            ps['id'] = int(ps['url'].split('/')[-2])
            ps['submitter'] = self.get_patchset_submitter(ps)
            if 'time_to_last_test' in ps:
                ps['time_to_last_test'] = format_timedelta(
                    timedelta(seconds=float(ps['time_to_last_test'])))
        return context


class DashboardDetail(BaseDashboardView):
    """Display the details for a particular patchset on the dashboard."""

    template_name = 'detail.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     'patchsets/' + str(self.kwargs['id'])))
            if api_resp.status_code == HTTPStatus.NOT_FOUND:
                raise Http404
            context['patchset'] = api_resp.json()
            context['patchset']['date'] = parse_datetime(
                context['patchset']['patches'][0]['date'])
            context['patchset']['submitter'] = self.get_patchset_submitter(
                context['patchset'])
            api_resp = s.get(urljoin(settings.API_BASE_URL, 'environments'),
                         params={'active': 'true'})
            if api_resp.status_code in [HTTPStatus.UNAUTHORIZED,
                                        HTTPStatus.FORBIDDEN]:
                envs = dict()
            else:
                api_resp.raise_for_status()
                envs = api_resp.json()['results']
                envs = {x['url']: x for x in envs}
            context['runs'] = dict()
            if context['patchset'].get('tarballs', []):
                tarball = s.get(context['patchset']['tarballs'][-1]).json()
                if tarball.get('date'):
                    tarball['date'] = parse_datetime(tarball['date'])
                context['tarball'] = tarball
                context['runs'] = {x: None for x in envs}
                for url in tarball['runs']:
                    resp = s.get(url)
                    if resp.status_code >= HTTPStatus.BAD_REQUEST:
                        continue
                    run = resp.json()
                    if run['log_upload_file']:
                        run['log_upload_file'] = build_upload_url(
                            self.request, run['log_upload_file'])
                    run['timestamp'] = parse_datetime(run['timestamp'])
                    delta = run['timestamp'] - context['patchset']['date']
                    run['timedelta'] = format_timedelta(delta)
                    run['failure_count'] = 0
                    run['testcases'] = {}
                    for result in run['results']:
                        measurement = s.get(result['measurement']).json()
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
                    env = s.get(env_url).json()
                    while (env_url not in context['runs'].keys() and
                           env.get('successor')):
                        env_url = env['successor']
                        env = s.get(env_url).json()
                    if env.get('live_since'):
                        env['live_since'] = parse_datetime(env['live_since'])
                    # parse the absolute url to our proxied url
                    if env.get('hardware_description'):
                        env['hardware_description'] = build_upload_url(
                            self.request, env['hardware_description'])
                    run['environment'] = env
                    context['runs'][env_url] = run

            # Fill in details of missing environments so they can be displayed
            # in the template
            for env_url, run in context['runs'].items():
                if run is None:
                    context['runs'][env_url] = {
                        'environment': envs[env_url]
                    }
            context['status_classes'] = text_color_classes(context['patchset']['status_class'])
            return context

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


class Preferences(LoginRequiredMixin, View):
    """Show user preferences."""

    def get(self, *args, **kwargs):
        """Redirect the user to the subscriptions page for now."""
        return HttpResponseRedirect(reverse('subscriptions'))


class Subscriptions(LoginRequiredMixin, BaseDashboardView):
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
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     'environments/'))
            environments = api_resp.json()

        # [{"environment": Foo, "subscription": None}]
        env_sub_pairs = []

        for env in environments['results']:
            # don't show old environments
            if env['successor'] is not None:
                continue
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


class PasswordChangeView(BaseDashboardView, auth_views.PasswordChangeView):
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


class PasswordChangeDoneView(BaseDashboardView, auth_views.PasswordChangeDoneView):
    """Inherit BaseDashboardView for context."""


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
            return HttpResponse(r, content_type=r.headers['content-type'])
