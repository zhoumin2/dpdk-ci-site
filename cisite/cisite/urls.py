"""cisite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""

from django.contrib import admin
from django.urls import include, path
from results.views import PatchSetViewSet, PatchViewSet, TarballViewSet, \
    EnvironmentViewSet, MeasurementViewSet, \
    TestRunViewSet, GroupViewSet
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view

router = DefaultRouter()
router.register(r'patchsets', PatchSetViewSet)
router.register(r'patches', PatchViewSet)
router.register(r'tarballs', TarballViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'measurements', MeasurementViewSet)
router.register(r'testruns', TestRunViewSet)
router.register(r'group', GroupViewSet)

schema_view = get_schema_view(title='DPDK CI Site API')

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls',
                              namespace='rest_framework')),
    path('admin/', admin.site.urls),
    path('schema/', schema_view),
]
