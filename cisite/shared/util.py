from django.http import HttpResponse


def requests_to_response(r):
    """Converts Requests Lib Response to Django Response."""
    return HttpResponse(content=r.content,
                        status=r.status_code,
                        content_type=r.headers['Content-Type'])
