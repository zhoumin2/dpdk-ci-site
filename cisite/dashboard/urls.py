"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define URL Configuration for dashboard app.

For dashboard to result API mapping, use an underscore (_) instead of a
dash (-), since the DRF uses a dash to separate words.
For example:
patchset-detail -> Results API URL
patchset_detail -> Dashboard URL
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, re_path, include
from django.views.decorators.cache import cache_page, cache_control
from django.views.decorators.vary import vary_on_cookie
from . import views

urlpatterns = [
    path('',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.PatchSetList.as_view()))),
         name='dashboard'),
    path('patchsets/',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.PatchSetList.as_view()))),
         name='patchset_list'),
    path('accounts/login/', views.LoginView.as_view(),
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(),
         name='logout'),
    path('patchsets/<int:id>/',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.PatchSetDetail.as_view()))),
         name='patchset_detail'),
    path('testruns/<int:tr_id>/rerun/',
         views.Rerun.as_view(),
         name='dashboard_rerun'),
    path('patchset/<int:ps_id>/rebuild/',
         views.Rebuild.as_view(),
         name='dashboard_rebuild'),
    re_path(settings.PRIVATE_STORAGE_URL[1:] + '(?P<path>.*)',
            views.UploadView.as_view(), name='dashboard-uploads'),
    path('js_error_hook/', include('django_js_error_hook.urls')),
    path('preferences/',
         views.Preferences.as_view(),
         name='preferences'),
    path('preferences/subscriptions/',
         views.Subscriptions.as_view(),
         name='subscriptions'),
    path('preferences/subscriptions/<int:subscription>/',
         views.Subscriptions.as_view(),
         name='subscriptions-detail'),
    path('preferences/password_change/',
         views.PasswordChangeView.as_view(),
         name='password_change'),
    path('preferences/password_change_done/',
         views.PasswordChangeDoneView.as_view(),
         name='password_change_done'),
    path('preferences/rest_api/',
         views.RESTAPIPreferences.as_view(),
         name='rest_api_preferences'),
    path('stats/',
         views.StatsView.as_view(),
         name='stats'),
    path('about/',
         views.AboutView.as_view(),
         name='about'),
    path('row/<int:offset>/',
         views.PatchSetRow.as_view(),
         name='patchset-row'),
    path('patchsets/row/<int:offset>/',
         views.PatchSetRow.as_view(),
         name='patchset-row'),
    path('tarballs/',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.TarballList.as_view()))),
         name='tarball_list'),
    path('tarballs/<int:id>/',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.TarballDetail.as_view()))),
         name='tarball_detail'),
    path('tarballs/<int:pk>/<str:filename>',
         views.CIDownloadView.as_view(), name='tarball-download'),
    path('status/',
         views.CIStatusView.as_view(), name='ci-status'),
    path('preferences/manage_users/',
         views.ManageUsers.as_view(),
         name='manage_users'),
    path('preferences/manage_users/<str:user>/remove_from_group/<str:group>/',
         views.ManageUsersRemove.as_view(),
         name='manage_users_remove'),
    path('preferences/manage_users/add_to_group/<str:group>/',
         views.ManageUsersAdd.as_view(),
         name='manage_users_add'),
    path('preferences/manage_environments/',
         views.ManageEnvironments.as_view(),
         name='manage_environments'),
    path('preferences/manage_environments/<int:env>/set_visibility',
         views.ManageEnvironmentVisibility.as_view(),
         name='environment_set_visibility'),
]
