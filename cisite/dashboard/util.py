"""Define extra utility methods for the dashboard."""

from contextlib import contextmanager
from django.conf import settings
from requests import Session
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin


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
