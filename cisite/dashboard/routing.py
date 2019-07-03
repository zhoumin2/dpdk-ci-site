"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.
"""

from django.conf.urls import url

from . import consumers

websocket_urlpatterns = [
    url(r'^ws/manage-environment/$', consumers.ManageEnvironmentConsumer),
]
