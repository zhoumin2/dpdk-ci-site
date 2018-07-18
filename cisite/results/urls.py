"""Configure Django URLconf for results app."""

from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import models
from . import views

router = DefaultRouter()
router.register(r'patchsets', views.PatchSetViewSet)
router.register(r'patches', views.PatchViewSet)
router.register(r'tarballs', views.TarballViewSet)
router.register(r'branches', views.BranchViewSet)
router.register(r'environments', views.EnvironmentViewSet)
router.register(r'measurements', views.MeasurementViewSet)
router.register(r'testcases', views.TestCaseViewSet)
router.register(r'testruns', views.TestRunViewSet)
router.register(r'group', views.GroupViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'subscriptions', views.SubscriptionViewSet)
router.register(r'statuses', views.StatusViewSet,
                base_name=r'status')


def upload_model_path(model, field):
    """Get uploaded files based on their model name, primary key, and field.

    This is utilized for private storage. models.upload_model_path will also
    have to be updated if this gets changed.
    """
    return f'{settings.PRIVATE_STORAGE_ROOT}{model._meta.verbose_name_plural}/<pk>/{field}/<filename>'


urlpatterns = [
    path('', include(router.urls)),
    path(upload_model_path(models.Environment, 'hardware_description'),
         views.HardwareDescriptionDownloadView.as_view(),
         name='hardware_description'),
]
