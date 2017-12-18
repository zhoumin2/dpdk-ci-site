"""Register admin interface for DPDK CI site results models."""
from django.contrib import admin
from .models import Patch, PatchSet

admin.site.register(Patch)
admin.site.register(PatchSet)
