"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define URL Configuration for cisite.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.schemas import get_schema_view
import private_storage.urls

urlpatterns = []

if getattr(settings, 'ENABLE_REST_API', True):
    urlpatterns.append(path('api-auth/', include('rest_framework.urls',
                                                 namespace='rest_framework')))
    schema_view = get_schema_view(title='DPDK CI Site API')
    urlpatterns.append(path('schema/', schema_view))
    urlpatterns.append(path('', include('results.urls')))

if getattr(settings, 'ENABLE_ADMIN', True):
    urlpatterns.append(path('admin/', admin.site.urls))

urlpatterns.append(path('dashboard/', include('dashboard.urls')))
urlpatterns.append(path(settings.PRIVATE_STORAGE_URL[1:], include(private_storage.urls)))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
