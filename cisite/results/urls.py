"""Configure Django URLconf for results app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'patchsets', views.PatchSetViewSet)
router.register(r'patches', views.PatchViewSet)
router.register(r'tarballs', views.TarballViewSet)
router.register(r'branches', views.BranchViewSet)
router.register(r'environments', views.EnvironmentViewSet)
router.register(r'measurements', views.MeasurementViewSet)
router.register(r'testruns', views.TestRunViewSet)
router.register(r'group', views.GroupViewSet)
router.register(r'users', views.UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
