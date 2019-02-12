"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define signal handlers for dashboard.
"""

from urllib.parse import urljoin
from django.conf import settings
from django.contrib.auth import user_logged_out
from django.contrib.auth.models import User
from django.dispatch import receiver
from .util import api_session


@receiver(user_logged_out, sender=User)
def on_logout(sender, request, user, **kwarg):
    """End API session for user when they log out."""
    with api_session(request) as s:
        s.get(urljoin(settings.API_BASE_URL, 'api-auth/logout'))
