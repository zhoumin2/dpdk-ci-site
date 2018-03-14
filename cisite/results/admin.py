"""Register admin interface for DPDK CI site results models."""
from django.contrib import admin
from .models import ContactPolicy, Environment, Measurement, Patch, PatchSet, \
    Tarball, TestResult, TestRun
from guardian.admin import GuardedModelAdmin

admin.site.register(ContactPolicy)
admin.site.register(Environment, GuardedModelAdmin)
admin.site.register(Measurement, GuardedModelAdmin)
admin.site.register(Patch)
admin.site.register(PatchSet)
admin.site.register(Tarball)
admin.site.register(TestResult, GuardedModelAdmin)
admin.site.register(TestRun, GuardedModelAdmin)
