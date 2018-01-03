"""Define test cases for results app."""

import datetime
import pytz
from django.test import TestCase
from results.models import Patch, PatchSet

# Create your tests here.
class ModelTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_ps = PatchSet(patchworks_id=30741, patch_count=3)
        cls.test_ps.save()
        Patch(patchworks_id=30741,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: extract xstat basic stat count calculation',
              patchset=cls.test_ps,
              version='v2',
              patch_number=1,
              date=datetime.datetime(2017, 10, 23, 23, 15, 32,
                                     tzinfo=pytz.utc)).save()
        Patch(patchworks_id=30742,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: fix xstats get by id APIS',
              patchset=cls.test_ps,
              version='v2',
              patch_number=2,
              date=datetime.datetime(2017, 10, 23, 23, 15, 33,
                                     tzinfo=pytz.utc)).save()

    def test_incomplete_patch_set(self):
        self.assertEqual(str(self.__class__.test_ps), '30741 2/3')

    def test_complete_patch_set(self):
        Patch(patchworks_id=30743,
              submitter='Ferruh Yigit <ferruh.yigit@intel.com>',
              subject='ethdev: fix xstats get by id APIS',
              patchset=self.__class__.test_ps,
              version='v2',
              patch_number=2,
              date=datetime.datetime(2017, 10, 23, 23, 15, 34,
                                     tzinfo=pytz.utc)).save()
        self.assertEqual(str(self.__class__.test_ps), '30741 3/3')
