"""Model data for patchsets, environments, and test results."""

from django.db import models


class PatchSet(models.Model):
    """Model a single patchset."""

    patchworks_id = models.IntegerField(unique=True)
    branch = models.CharField(max_length=64)
    commit_id = models.CharField('git commit hash', max_length=40)
    tarball = models.CharField(max_length=256)
    patch_count = models.IntegerField()

    def __str__(self):
        """Return string representation of patchset record."""
        return 'PatchSet ID={pid:d} Count={count:d}'.format(
            pid=self.patchworks_id, count=len(self.patches.values()))


class Patch(models.Model):
    """Model a single patch in PatchWorks."""

    patchworks_id = models.IntegerField(unique=True)
    submitter = models.CharField(max_length=128)
    subject = models.CharField(max_length=128)
    patchset = models.ForeignKey(PatchSet, on_delete=models.CASCADE,
                                 related_name='patches')
    version = models.CharField(max_length=16)
    patch_number = models.IntegerField()
    date = models.DateTimeField('date submitted')

    def __str__(self):
        """Return string representation of patch record."""
        return '[PATCH,{pid:d},{number:d},{count:d}] {subject:s}'.format(
            pid=self.patchworks_id, subject=self.subject,
            number=self.patch_number, count=self.patchset.patch_count)
