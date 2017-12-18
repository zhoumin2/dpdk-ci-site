"""Configure Django URLconf for results app."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('patchsets/', views.handle_patchsets),
    path('patchsets/<int:patchset_id>/',
         views.get_one_patchset, name='patchset'),
    path('patchsets/<int:patchset_id>/patches/', views.add_patch_to_patchset,
         name='patchset_new_patch'),
    path('patchsets/<int:patchset_id>/patches/<int:patch_psid>/',
         views.get_patchset_patch, name='patchset_patch'),
]
