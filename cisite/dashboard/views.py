"""Define dashboard views."""

from urllib.parse import urljoin
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.http import HttpResponseServerError
from guardian.shortcuts import get_objects_for_user

from results.models import Environment
from .util import api_session


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
            r = s.get(login_url)
            if r.status_code >= 400:
                return HttpResponseServerError(
                    content='Unable to login to backend API')
            r = s.post(login_url,
                       data={'username': form.cleaned_data['username'],
                             'password': form.cleaned_data['password'],
                             'csrfmiddlewaretoken': r.cookies['csrftoken'],
                             'next': '/'},
                       allow_redirects=False)
            if r.status_code >= 400:
                return HttpResponseServerError(
                    content='Unable to login to backend API')
            self.request.session['api_sessionid'] = r.cookies['sessionid']
            return endresp


class PatchSetList(TemplateView):
    """Display the list of patches on the dashboard."""

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            resp = s.get(urljoin(settings.API_BASE_URL, 'patchsets'))
            resp.raise_for_status()
            context['patchsets'] = resp.json()['results']
        for ps in context['patchsets']:
            ps['id'] = int(ps['url'].split('/')[-2])
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
        return context


class DashboardDetail(TemplateView):
    """Display the details for a particular patchset on the dashboard."""

    template_name = 'detail.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        with api_session(self.request) as s:
            api_resp = s.get(urljoin(settings.API_BASE_URL,
                                     'patchsets/' + str(self.kwargs['id'])))
            context['patchset'] = api_resp.json()
        if 'tarballs' in context['patchset']:
            tarball = s.get(context['patchset']['tarballs'][-1]).json()
            context['runs'] = list()
            for url in tarball['runs']:
                resp = s.get(url)
                if resp.status_code >= 400:
                    continue
                run = resp.json()
                run['failure_count'] = 0
                for result in run['results']:
                    result['measurement'] = s.get(result['measurement']).json()
                    if result['result'].upper() == 'FAIL':
                        run['failure_count'] += 1
                run['environment'] = s.get(run['environment']).json()
                context['runs'].append(run)
        context['status_classes'] = text_color_classes(context['patchset']['status_class'])
        return context


class Preferences(LoginRequiredMixin, TemplateView):
    """Show user preferences for the environments."""

    template_name = 'preferences.html'

    def get_context_data(self, **kwargs):
        """Return contextual data about the available preferences."""
        context = super().get_context_data(**kwargs)
        subscriptions =\
            self.request.user.results_profile.subscription_set.all()
        environments = get_objects_for_user(self.request.user,
            'view_environment',
            Environment.objects.all(),
            accept_global_perms=False)

        # [{"environment": Foo, "subscription": None}]
        env_sub_pairs = []

        for env in environments:
            sub = subscriptions.filter(environment__exact=env).first()
            # sub gets set to None if a subscription for the environment does
            # not exist
            env_sub_pairs.append({'environment': env, 'subscription': sub})

        context['env_sub_pairs'] = env_sub_pairs
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
        return context
