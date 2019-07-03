"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.

Define extra utility methods for the dashboard.
"""

import json
from contextlib import contextmanager
from html.parser import HTMLParser
from logging import getLogger
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from requests import Session
from requests.adapters import HTTPAdapter

# default logger
logger = getLogger('dashboard')
# used for development url mapping
request_mapping = None


@contextmanager
def api_session(request):
    with Session() as s:
        s.mount('http://', HTTPAdapter(max_retries=2))
        s.mount('https://', HTTPAdapter(max_retries=2))
        if 'csrftoken' in request.COOKIES:
            s.cookies['csrftoken'] = request.COOKIES['csrftoken']
            s.headers.update({'X-CSRFToken': request.META.get('CSRF_COOKIE')})
        s.headers.update({'Referer': request.build_absolute_uri()})
        if hasattr(settings, 'CA_CERT_BUNDLE'):
            s.verify = settings.CA_CERT_BUNDLE
        if request.user.is_authenticated and 'api_sessionid' in request.session:
            s.cookies['sessionid'] = request.session['api_sessionid']
        yield s


def format_timedelta(delta):
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}h {minutes}m {seconds}s'


@contextmanager
def ipa_session(username, password):
    """Create an IPA session.

    Returns:
        session: The ipa session to use for further requests
        resp: The response when creating the session. The user MUST check that
            this response was valid and handle appropriately!
        ipa_url: The ipa url gathered from the settings
    """
    with Session() as session:
        session.verify = settings.CA_CERT_BUNDLE
        ipa_url = settings.IPA_URL
        session.headers.update({'referer': ipa_url})

        data = {'user': username, 'password': password}
        resp = session.post(urljoin(ipa_url, 'session/login_password'),
                            data=data)
        yield session, resp, ipa_url


class ParseIPAChangePassword(HTMLParser):
    """Parse password change page from IPA.

    (session/change_password)
    """

    _record_header = False
    _record_message = False

    def handle_starttag(self, tag, attrs):
        """Handle HTML start tags."""
        if tag == 'h1':
            self._record_header = True
        elif tag == 'strong':
            self._record_message = True

    def handle_endtag(self, tag):
        """Handle HTML end tags."""
        if tag == 'h1':
            self._record_header = False
        elif tag == 'strong':
            self._record_message = False

    def handle_data(self, data):
        """Handle HTML data between tags."""
        if self._record_header:
            self._header = data
        elif self._record_message:
            self._message = data

    @property
    def header(self):
        """Get the header."""
        return self._header

    @property
    def message(self):
        """Get the message."""
        return self._message


def build_upload_url(request, real_url):
    """Returns a url based on the app and to-proxy url."""
    return request.build_absolute_uri(
        reverse('dashboard') + urlparse(real_url).path[1:])


def pw_get(url, session=None):
    """Calls a GET request to the patchworks API.

    This also caches the response for future usage for an arbitrary amount.

    `url` is a url to the patchworks API.
    `session` is a requests Session. If passed, it is expected that it is
        closed by the callee.

    Returns: JSON response or throws an exception if the connection failed.
    """
    if settings.ENVIRONMENT == 'development':
        try:
            return _pw_get_devel(url)
        except KeyError:
            logger.warn(f'THIS SHOULD BE CACHED FOR DEVELOPMENT: {url}')

    def call_pw_json():
        logger.info(f'Requesting patchworks url: {url}')
        if not session:
            with Session() as s:
                resp = s.get(url)
        else:
            resp = session.get(url)
        resp.raise_for_status()
        return resp.json()
    # cache for 6 hours
    return cache.get_or_set(url, call_pw_json, 60 * 60 * 6)


def _pw_get_devel(url):
    """If running in devel, use a mapping instead of calling patchworks."""
    global request_mapping
    if not request_mapping:
        with open('cisite/request_mapping.json', 'r') as f:
            request_mapping = json.load(f)
    return request_mapping[url]
