"""Define URL Configuration for dashboard app."""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.PatchSetList.as_view(), name='dashboard'),
    path('accounts/login/', views.LoginView.as_view(),
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(),
         name='logout'),
    path('patchsets/<int:id>/', views.DashboardDetail.as_view(),
         name='dashboard-detail'),
]

if getattr(settings, 'ENABLE_PREFERENCES', True):
    urlpatterns.append(path('preferences/',
                            views.Preferences.as_view(),
                            name='preferences'))
    urlpatterns.append(path('preferences/subscriptions/',
                            views.Subscriptions.as_view(),
                            name='subscriptions'))
    urlpatterns.append(path('preferences/subscriptions/<int:subscription>/',
                            views.Subscriptions.as_view(),
                            name='subscriptions-detail'))
    urlpatterns.append(path('preferences/password_change/',
                            views.PasswordChangeView.as_view(),
                            name='password_change'))
    urlpatterns.append(path('preferences/password_change_done/',
                            views.PasswordChangeDoneView.as_view(),
                            name='password_change_done'))
