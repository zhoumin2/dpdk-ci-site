"""Define URL Configuration for dashboard app."""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.PatchSetList.as_view(), name='dashboard'),
    path('patchsets/<int:id>/', views.DashboardDetail.as_view(),
         name='dashboard-detail'),
    path('preferences/', views.Preferences.as_view(), name='preferences'),
]
