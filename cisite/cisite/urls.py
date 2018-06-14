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

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework.schemas import get_schema_view

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
