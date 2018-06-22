"""Define URL Configuration for dashboard app."""

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
    path('preferences/', views.Preferences.as_view(), name='preferences'),
]