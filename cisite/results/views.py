"""Render views for results database objects."""

from django.http import HttpResponse, HttpResponseBadRequest,\
    HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from .models import PatchSet, Patch
import json


class HttpResponseConflict(HttpResponse):
    """Return status 409 Conflict in response to a POST request."""

    status_code = 409


# Create your views here.
def index(request):
    """Render a simple HTTP view of the root object."""
    return HttpResponse("""<html>
<head>
  <title>Results</title>
</head>
<body>
  <ul>
    <li><a href=\"patchsets/\">Patchsets</a></li>
  </ul>
</body>
</html>
""")


def get_patchsets(request):
    """Render a simple list of all available patchsets."""
    patchsets = PatchSet.objects.order_by('patchworks_id')
    output = ', '.join([str(p) for p in patchsets])
    return HttpResponse(output)


def post_patchset(request):
    """Handle POST request for new patchset."""
    jsondata = json.loads(request.body)
    dup = PatchSet.objects.filter(patchworks_id=jsondata['patchworks_id'])
    if dup.exists():
        return HttpResponseConflict(json.dumps(dict(reason='Duplicate patchworks_id',
                                                    url=request.build_absolute_uri(reverse('patchset',
                                                                                           args=[dup[0].id])))))
    ps = PatchSet(patchworks_id=jsondata['patchworks_id'],
                  branch="", commit_id="", tarball="",
                  patch_count=jsondata['patch_count'])
    ps.save()
    resp = dict(url=reverse('patchset', args=[ps.id]))
    return JsonResponse(resp)


@csrf_exempt
def handle_patchsets(request):
    """Handle any HTTP request for patchsets root."""
    if request.method == 'POST':
        return post_patchset(request)
    elif request.method == 'GET':
        return get_patchsets(request)
    else:
        return HttpResponseNotAllowed(['GET'], ['POST'])


def get_one_patchset(request, patchset_id):
    """Handle HTTP request for a specific patchset."""
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    ps = PatchSet.objects.get(id=patchset_id)
    return JsonResponse(dict(id=ps.id,
                             patchworks_id=ps.patchworks_id,
                             patch_count=ps.patch_count,
                             url=request.build_absolute_uri(reverse('patchset', args=[ps.id])),
                             patches_url=request.build_absolute_uri(reverse('patchset_new_patch', args=[ps.id]))))


@csrf_exempt
def add_patch_to_patchset(request, patchset_id):
    """Handle HTTP request to add a patch to an existing patchset."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    jsondata = json.loads(request.body)
    dup = Patch.objects.filter(patchworks_id=jsondata['patchworks_id'])
    if dup.exists():
        return HttpResponseConflict(json.dumps(dict(reason='Duplicate patchworks_id',
                                                    url=request.build_absolute_uri(reverse(
                                                        'patchset_patch',
                                                        args=[patchset_id, dup[0].id])))))
    p = Patch(patchworks_id=jsondata['patchworks_id'],
              submitter=jsondata['submitter'],
              date=jsondata['date'],
              subject=jsondata['subject'],
              version=jsondata['version'],
              patchset_id=patchset_id,
              patch_number=jsondata['patch_number'])
    p.save()
    resp = dict(url=reverse('patchset_patch', args=[patchset_id, p.id]))
    return JsonResponse(resp)


def get_patchset_patch(request, patchset_id, patch_psid):
    """Handle HTTP request to get a single patch from a patchset."""
    ps = PatchSet.objects.get(id=patchset_id)
    values = ps.patch_set.values()
    if patch_psid < 1 or patch_psid > len(values):
        return HttpResponseBadRequest('patch_psid {0:d} out of range [0:{1:d}]'.format(patch_psid, len(values)))
    v = values[patch_psid - 1]
    v['date'] = str(v['date'])
    return HttpResponse(json.dumps(v))
