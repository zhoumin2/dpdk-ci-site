"""Define tests for dashboard app."""

from datetime import datetime
import pytz
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.http import Http404
from django.test import TestCase
from django.urls import reverse
import requests_mock
from results.tests import create_test_environment
from results.models import ContactPolicy, Patch, PatchSet, Measurement, \
    Parameter, Subscription, Tarball, TestResult, TestRun
from .views import paginate_rest, parse_page


class BaseTestCase(StaticLiveServerTestCase):
    """Base class for all dashboard test cases."""

    def tearDown(self):
        """Clear cache to fix an IntegrityError bug."""
        ContentType.objects.clear_cache()
        super().tearDown()


@requests_mock.Mocker()
class PatchListViewTests(BaseTestCase):
    """Test the patch list view."""

    def setUp(self):
        """Set up fake data into test database."""
        super().setUp()
        grp = Group.objects.create(name='acme')
        user = User.objects.create_user(username='acmevendor', first_name='John',
                                   last_name='Vendor',
                                   email='jvendor@example.com',
                                   password='P@$$w0rd')
        user.groups.add(grp)

    def setup_mock(self, m):
        """Set up the mock appropriately."""
        m.register_uri('GET', urljoin(settings.API_BASE_URL,
                                      'api-auth/login/'),
                       json='<html></html>',
                       cookies={'csrftoken': 'abcdefg'})
        m.register_uri('POST', urljoin(settings.API_BASE_URL,
                                      'api-auth/login/'),
                       json='<html></html>',
                       cookies={'sessionid': '01234567'})
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'statuses?'),
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [
                    {
                        'name': 'Pass',
                        'class': 'success',
                        'tooltip': 'Pass'
                    }
                ]
            })
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'patchsets?complete=true'),
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [
                    {
                        'url': urljoin(settings.API_BASE_URL,
                                       'patchsets/1/'),
                        'message_uid': '20180601110742.11927',
                        'patch_count': 1,
                        'patchwork_range_str': '40574',
                        'submitter_name': 'Thomas Monjalon',
                        'submitter_email': 'thomas@monjalon.net',
                        'status': 'Pass',
                        'status_class': 'success',
                        'status_tooltip': 'Pass',
                        'patches': [
                            {
                                'url': urljoin(settings.API_BASE_URL,
                                               'patches/1/'),
                                'patchworks_id': 40574,
                                'message_id': '20180601110742.11927-1-thomas@monjalon.net',
                                'subject': 'version: 18.08-rc0',
                                'patchset': urljoin(settings.API_BASE_URL,
                                                    'patchsets/1/'),
                                'version': 'v0',
                                'patch_number': 1,
                                'date': '2018-06-01 11:07:42+00:00',
                                'contacts': '[{"display_name": "", '
                                            '"email": "dev@dpdk.org", '
                                            '"how": "to"}]'
                            }
                        ]
                    }
                ]
            })

    def test_anon_active_legend(self, m):
        """Verify that the status legend is populated properly in context."""
        self.setup_mock(m)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        legend = response.context['statuses']
        self.assertEqual(legend[0]['name'], 'Pass')
        self.assertEqual(legend[0]['class'], 'success')
        self.assertEqual(legend[0]['tooltip'], 'Pass')

    def test_anon_active_patchset(self, m):
        """Verify that an active patch is shown in the anonymous view."""
        self.setup_mock(m)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchsets'][0]
        self.assertEqual(ps['id'], 1)
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(ps['patches'][0]['version'], 'v0')
        self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
        self.assertEqual(ps['submitter'], 'Thomas Monjalon')
        self.assertEqual(ps['status'], 'Pass')
        self.assertEqual(ps['status_class'], 'success')
        self.assertEqual(ps['status_tooltip'], 'Pass')

    def test_auth_active_patchset(self, m):
        """Verify that patchsets are shown properly in authenticated view.

        """
        self.setup_mock(m)
        response = self.client.post(
            reverse('login'),
            dict(username='acmevendor', password='P@$$w0rd'), follow=True)
        self.assertTrue(response.context['user'].is_active)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchsets'][0]
        self.assertEqual(ps['id'], 1)
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(ps['patches'][0]['version'], 'v0')
        self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
        self.assertEqual(ps['submitter'],
                         'Thomas Monjalon <thomas@monjalon.net>')
        self.assertEqual(ps['status'], 'Pass')
        self.assertEqual(ps['status_class'], 'success')
        self.assertEqual(ps['status_tooltip'], 'Pass')


class DetailViewTests(BaseTestCase):
    """Test the detail view."""

    def setUp(self):
        super().setUp()
        grp = Group.objects.create(name='acme')
        user = User.objects.create_user(username='acmevendor', first_name='John',
                                   last_name='Vendor',
                                   email='jvendor@example.com',
                                   password='P@$$w0rd')
        user.groups.add(grp)
        self.env = create_test_environment(owner=grp)
        ContactPolicy.objects.create(environment=self.env)
        self.m1 = Measurement.objects.create(name='throughput', unit='Mpps',
                                             higher_is_better=True,
                                             environment=self.env)
        Parameter.objects.create(name='frame_size', unit='bytes', value=64,
                                 measurement=self.m1)
        Parameter.objects.create(name='txd/rxd', unit='descriptors', value=64,
                                 measurement=self.m1)
        self.m2 = Measurement.objects.create(name='throughput', unit='Mpps',
                                             higher_is_better=True,
                                             environment=self.env)
        Parameter.objects.create(name='frame_size', unit='bytes', value=64,
                                 measurement=self.m2)
        Parameter.objects.create(name='txd/rxd', unit='descriptors', value=512,
                                 measurement=self.m2)

    def make_test_patchset(self, result2='PASS'):
        """Create a test patchset and test result."""
        ps = PatchSet.objects.create(message_uid='20180601110742.11927',
                                     patch_count=1)
        Patch.objects.create(
            patchworks_id=40574,
            message_id='20180601110742.11927-1-thomas@monjalon.net',
            submitter='Thomas Monjalon <thomas@monjalon.net>',
            subject='version: 18.08-rc0', patchset=ps, version='v0',
            patch_number=1, date='2018-06-01 11:07:42+00:00',
            contacts='[{"display_name": "", "email": "dev@dpdk.org", '
                     '"how": "to"}]')
        tb = Tarball.objects.create(
            branch='dpdk', build_id=914, job_name='Apply-One-Patch-Set',
            commit_id='c6266cd55c3ab3bd13711ac0ae599fcf4a32ce84',
            patchset=ps)

        run = TestRun.objects.create(
            timestamp=datetime(2018, 6, 1, 20, 27, 42, tzinfo=pytz.utc),
            log_output_file='https://dpdklab.iol.unh.edu/jenkins/job/'
                            'ACME1-Performance-Test/3/artifact/gamma.zip',
            tarball=tb, environment=self.env)
        TestResult.objects.create(result='PASS', difference=-0.185655863091204,
                                  measurement=self.m1, run=run)
        TestResult.objects.create(result=result2, difference=-0.664055231513893,
                                  measurement=self.m2, run=run)

        return ps

    def test_anon_load(self):
        """Test that the anonymous page loads."""
        ps = self.make_test_patchset()
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.get(reverse('dashboard-detail',
                                               args=[ps.id]))
            self.assertEqual(response.status_code, 200)
            ps = response.context['patchset']
            self.assertEqual(ps['patchwork_range_str'], '40574')
            self.assertEqual(len(ps['patches']), 1)
            self.assertEqual(ps['patches'][0]['patch_number'], 1)
            self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
            self.assertEqual(ps['status'], 'Pass')
            self.assertEqual(len(response.context['runs'].items()), 0)

    def test_auth_fail(self):
        """Test a result with a failing result."""
        ps = self.make_test_patchset(result2='FAIL')
        with self.settings(API_BASE_URL=self.live_server_url):
            # Log in
            response = self.client.post(reverse('login'),
                dict(username='acmevendor', password='P@$$w0rd'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('dashboard-detail',
                                               args=[ps.id]),
                                       follow=True)
            self.assertEqual(response.status_code, 200)
            ps = response.context['patchset']
            self.assertEqual(ps['patchwork_range_str'], '40574')
            self.assertEqual(len(ps['patches']), 1)
            self.assertEqual(ps['patches'][0]['patch_number'], 1)
            self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
            self.assertEqual(ps['status'], 'Possible Regression')
            run = response.context['runs'][
                urljoin(self.live_server_url, reverse('environment-detail',
                                                      args=[self.env.id]))]
            self.assertEqual(len(run['results']), 2)
            self.assertIsNot(run, None)
            self.assertEqual(run['environment']['id'], self.env.id)
            self.assertEqual(run['environment']['nic_model'], 'XL710')
            self.assertEqual(run['failure_count'], 1)
            self.assertEqual(run['results'][0]['result'], 'PASS')
            self.assertEqual(run['results'][1]['result'], 'FAIL')
            self.assertAlmostEqual(run['results'][0]['difference'],
                                   -0.185655, places=5)
            self.assertAlmostEqual(run['results'][1]['difference'],
                                   -0.664055, places=5)

    def test_auth_load(self):
        """Test that the authenticated page loads."""
        ps = self.make_test_patchset()
        with self.settings(API_BASE_URL=self.live_server_url):
            # Log in
            response = self.client.post(reverse('login'),
                dict(username='acmevendor', password='P@$$w0rd'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('dashboard-detail',
                                               args=[ps.id]),
                                       follow=True)
            self.assertEqual(response.status_code, 200)
            ps = response.context['patchset']
            self.assertEqual(ps['patchwork_range_str'], '40574')
            self.assertEqual(len(ps['patches']), 1)
            self.assertEqual(ps['patches'][0]['patch_number'], 1)
            self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
            self.assertEqual(ps['status'], 'Pass')
            run = response.context['runs'][
                urljoin(self.live_server_url, reverse('environment-detail',
                                                      args=[self.env.id]))]
            self.assertEqual(len(run['results']), 2)
            self.assertIsNot(run, None)
            self.assertEqual(run['environment']['id'], self.env.id)
            self.assertEqual(run['environment']['nic_model'], 'XL710')
            self.assertEqual(run['failure_count'], 0)
            self.assertEqual(run['results'][0]['result'], 'PASS')
            self.assertAlmostEqual(run['results'][0]['difference'],
                                   -0.185655, places=5)
            self.assertAlmostEqual(run['results'][1]['difference'],
                                   -0.664055, places=5)

    def test_auth_successor(self):
        """Verify that runs dictionary uses successor environment."""
        oldenv = self.env
        self.env = self.env.clone()
        try:
            ps = self.make_test_patchset()
            with self.settings(API_BASE_URL=self.live_server_url):
                # Log in
                response = self.client.post(reverse('login'),
                    dict(username='acmevendor', password='P@$$w0rd'), follow=True)
                self.assertTrue(response.context['user'].is_active)

                response = self.client.get(reverse('dashboard-detail',
                                                   args=[ps.id]),
                                           follow=True)
                self.assertEqual(response.status_code, 200)
                ps = response.context['patchset']
                self.assertEqual(ps['patchwork_range_str'], '40574')
                self.assertEqual(len(ps['patches']), 1)
                self.assertEqual(ps['patches'][0]['patch_number'], 1)
                self.assertEqual(ps['patches'][0]['subject'], 'version: 18.08-rc0')
                self.assertEqual(ps['status'], 'Pass')
                run = response.context['runs'][
                    urljoin(self.live_server_url, reverse('environment-detail',
                                                          args=[self.env.id]))]
                self.assertEqual(len(run['results']), 2)
                self.assertIsNot(run, None)
                self.assertEqual(run['environment']['id'], self.env.id)
                self.assertEqual(run['environment']['nic_model'], 'XL710')
                self.assertEqual(run['failure_count'], 0)
                self.assertEqual(run['results'][0]['result'], 'PASS')
                self.assertAlmostEqual(run['results'][0]['difference'],
                                       -0.185655, places=5)
                self.assertAlmostEqual(run['results'][1]['difference'],
                                       -0.664055, places=5)
        finally:
            self.env = oldenv


class PreferencesViewTests(BaseTestCase):
    """Test the preferences view."""

    def setUp(self):
        """Set up dummy test data."""
        super().setUp()
        self.user1 = User.objects.create_user('joevendor',
                                              'joe@example.com',
                                              'AbCdEfGh')
        self.user2 = User.objects.create_user('joevendor2',
                                              'joe2@example.com',
                                              'AbCdEfGh2')
        self.grp1 = Group.objects.create(name='Group1')
        self.grp2 = Group.objects.create(name='Group2')
        self.user1.groups.add(self.grp1)
        self.user2.groups.add(self.grp2)

    def test_anonymous_user(self):
        """Test the anonymous user gets redirected to the login page."""
        response = self.client.get(reverse('preferences'))
        self.assertEqual(response.status_code, 302)

    def test_no_env(self):
        """Test the template and returns an empty list."""
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'], [])

    def test_with_env(self):
        """Test the template and return a list."""
        env = create_test_environment(owner=self.grp1)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription'], None)

    def test_no_env_available(self):
        """Test the template and returns an empty list.

        Checks that the environment the user does not have access to does not
        show up in the list.
        """
        # Add an environment that the user does not have access to
        create_test_environment(owner=self.grp2)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'], [])

    def test_env_with_subscription(self):
        """Test the template and return an env:sub pair."""
        env = create_test_environment(owner=self.grp1)
        sub = Subscription.objects.create(
            user_profile=self.user1.results_profile, environment=env,
            email_success=False)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription']['id'], sub.id)

    def test_env_with_no_subscription(self):
        """Test the template and permissions between subscriptions."""
        # create user3 with access to env
        user = User.objects.create_user('joevendor3',
                                        'joe3@example.com', 'AbCdEfGh3')
        user.groups.add(self.grp1)
        env = create_test_environment(owner=self.grp1)
        # create sub with user3
        Subscription.objects.create(
            user_profile=user.results_profile, environment=env,
            email_success=False)

        # but login with user1, who has access to env
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('preferences'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription'], None)


class PaginationTests(TestCase):
    """Test the pagination.

    These are somewhat minimal since we are utiling the Django REST methods.
    """

    def test_valid_case(self):
        """Test that nothing breaks under normal circumstances."""
        context = {}
        paginate_rest(parse_page(5), context, 20)
        self.assertEqual(context['next'], '?page=6')
        self.assertEqual(context['previous'], '?page=4')

        context = {}
        paginate_rest(parse_page(10), context, 20)
        self.assertIsNone(context['next'])
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(1), context, 20)
        self.assertEqual(context['next'], '?page=2')
        self.assertIsNone(context['previous'])

        context = {}
        paginate_rest(parse_page(1), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

        # check ceil properly
        context = {}
        paginate_rest(parse_page(1), context, 3)
        self.assertEqual(context['next'], '?page=2')
        self.assertIsNone(context['previous'])

    def test_zero_index(self):
        """Test that zero gets converted to page 1."""
        context = {}
        paginate_rest(parse_page(0), context, 20)
        self.assertEqual(context['next'], '?page=2')

        context = {}
        paginate_rest(parse_page(0), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

    def test_negatives(self):
        """Test that wrapping occurs."""
        context = {}
        paginate_rest(parse_page(-1), context, 20)
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(-11), context, 20)
        self.assertEqual(context['previous'], '?page=9')

        context = {}
        paginate_rest(parse_page(-1), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

        context = {}
        paginate_rest(parse_page(-11), context, 2)
        self.assertIsNone(context['next'])
        self.assertIsNone(context['previous'])

    def test_pages_greater_than_page(self):
        """Test that we get a 404 if page > pages."""
        with self.assertRaises(Http404):
            paginate_rest(parse_page(11), {}, 20)

        with self.assertRaises(Http404):
            paginate_rest(parse_page(2), {}, 2)
