from django.conf import settings
from django.views.generic import ListView, TemplateView
from django.shortcuts import get_object_or_404
from guardian.shortcuts import get_objects_for_user
from results.models import PatchSet, TestRun, Environment
from django.contrib.auth.mixins import LoginRequiredMixin


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


class PatchSetList(ListView):
    """Display the list of patches on the dashboard."""

    context_object_name = 'patchsets'
    queryset = PatchSet.objects.complete().exclude(patches__pw_is_active=False)
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        """Return extra data for the dashboard template."""
        context = super().get_context_data(**kwargs)
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
        return context


class DashboardDetail(ListView):
    """Display the details for a particular patchset on the dashboard."""

    context_object_name = 'runs'
    pk_url_kwarg = 'id'
    queryset = PatchSet.objects.complete().exclude(patches__pw_is_active=False)
    template_name = 'detail.html'

    def get_queryset(self):
        """Return a filtered queryset of test runs the user has access to."""
        self.patchset = get_object_or_404(PatchSet, id=self.kwargs['id'])
        tarball = self.patchset.tarballs.last()
        if tarball is None:
            return TestRun.objects.none()
        else:
            return get_objects_for_user(self.request.user, 'view_testrun',
                                        tarball.runs.all(),
                                        accept_global_perms=False)

    def get_context_data(self, **kwargs):
        """Return contextual data about the patchset for the test runs."""
        context = super().get_context_data(**kwargs)
        self.patchset = get_object_or_404(PatchSet, id=self.kwargs['id'])
        context['patchset_range'] = self.patchset.patchwork_range_str()
        context['patches'] = self.patchset.patches.all()
        context['status'] = self.patchset.status()
        context['status_classes'] = text_color_classes(self.patchset.status_class())
        context['banner'] = getattr(settings, 'DASHBOARD_BANNER', None)
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
