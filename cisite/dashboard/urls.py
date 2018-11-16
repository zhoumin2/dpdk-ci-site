"""Define URL Configuration for dashboard app."""

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
    path('accounts/login/', views.LoginView.as_view(),
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(),
         name='logout'),
    path('patchsets/<int:id>/',
         cache_control(private=True)(
             vary_on_cookie(
                 cache_page(60 * 10)(
                     views.DashboardDetail.as_view()))),
         name='dashboard-detail'),
    path('testruns/<int:tr_id>/rerun/',
         views.Rerun.as_view(),
         name='dashboard_rerun'),
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
    path('stats/',
         views.StatsView.as_view(),
         name='stats'),
]
