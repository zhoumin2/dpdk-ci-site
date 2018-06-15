"""Define extra utility methods for the dashboard."""

from contextlib import contextmanager
from requests import Session
from requests.adapters import HTTPAdapter


@contextmanager
def api_session(request):
    with Session() as s:
        s.mount('http://', HTTPAdapter(max_retries=2))
        s.mount('https://', HTTPAdapter(max_retries=2))
        if request.user.is_authenticated and 'api_sessionid' in request.session:
            s.cookies['sessionid'] = request.session['api_sessionid']
        yield s
