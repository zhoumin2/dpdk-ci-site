"""Define tests for dashboard app."""

import json

from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.http import Http404
from django import test
from django.urls import reverse
import requests_mock
from results.tests import create_test_environment
from results.models import Subscription, TestCase
from .views import paginate_rest, parse_page
from .util import ParseIPAChangePassword


class BaseTestCase(StaticLiveServerTestCase):
    """Base class for all dashboard test cases."""

    def tearDown(self):
        """Clear cache to fix an IntegrityError bug."""
        ContentType.objects.clear_cache()
        super().tearDown()

    def setup_mock_common(self, m):
        """Use for anonymous request mocking."""
        m.register_uri('GET', urljoin(settings.API_BASE_URL,
                                      'api-auth/login/'),
                       json='<html></html>',
                       cookies={'csrftoken': 'abcdefg'})
        m.register_uri('POST', urljoin(settings.API_BASE_URL,
                                      'api-auth/login/'),
                       json='<html></html>',
                       cookies={'sessionid': '01234567'})
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'statuses/'),
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
            'GET', urljoin(settings.API_BASE_URL, 'tarballs/1/'),
            json={
                'id': 1,
                'url': urljoin(settings.API_BASE_URL, 'tarballs/1/'),
                'patchset': urljoin(settings.API_BASE_URL, 'patchsets/1/'),
                'branch': 'dpdk',
                'commit_id': 'ee73f98ef481f61eab2f7289f033c6f9113eee8a',
                'job_name': 'Apply-One-Patch-Set',
                'build_id': 936,
                'tarball_url': urljoin(settings.JENKINS_URL, 'job/Get-Latest-Git-Master/26/artifact/dpdk.tar.gz'),
                'runs': [
                    urljoin(settings.API_BASE_URL, 'testruns/1/'),
                ],
                'date': '2018-07-25T17:29:27.556679Z',
                'commit_url': 'https://git.dpdk.org/dpdk/commit/?id=ee73f98ef481f61eab2f7289f033c6f9113eee8a'
            })
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'testcases/1/'),
            json={
                'url': urljoin(settings.API_BASE_URL, 'testcases/1/'),
                'name': 'nic_single_core_perf',
                'description_url':
                    'http://git.dpdk.org/tools/dts/tree/test_plans/nic_single_core_perf_test_plan.rst?h=next'
            })
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'group/3/'),
            json={
                'url': urljoin(settings.API_BASE_URL, 'group/3/'),
                'name': 'acme',
            })
        with open('cisite/request_mapping.json') as f:
            mapping = json.load(f)
            url = urljoin(settings.PATCHWORKS_URL, 'series/1')
            m.register_uri('GET', url, json=mapping[url])

    def setup_mock_anonymous(self, m):
        """Set up the mock for anonymous users."""
        self.setup_mock_common(m)
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'environments/?active=true'),
            status_code=401)
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'testruns/1/'),
            status_code=401)
        ps_1 = {
            'url': urljoin(settings.API_BASE_URL, 'patchsets/1/'),
            'id': 1,
            'is_public': True,
            'apply_error': False,
            'tarballs': [
                urljoin(settings.API_BASE_URL, 'tarballs/1/')
            ],
            'status': 'Pass',
            'status_class': 'success',
            'status_tooltip': 'Pass',
            'series_id': 1,
            'pw_series_url': urljoin(settings.PATCHWORKS_URL, 'series/1'),
            'completed_timestamp': '2018-07-20T00:00:00Z',
            'incomplete': 0,
            'passed': 0,
            'failed': 0,
            'build_error': False,
            'has_error': False
        }
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL,
                           'patchsets/?pw_is_active=true&without_series=false&ordering=-id&offset=0'),
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [ps_1]
            })
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'patchsets/1/'),
            json=ps_1)
        return ps_1

    def setup_mock_authenticated(self, m):
        """Set up the mock for logged in users."""
        self.setup_mock_common(m)
        measurement = {
            'url': urljoin(settings.API_BASE_URL, 'measurements/1/'),
            'id': 1,
            'name': 'throughput',
            'unit': 'Mpps',
            'higher_is_better': True,
            'environment': urljoin(settings.API_BASE_URL, 'environments/1/'),
            'parameters': [
                {
                    'name': 'frame_size',
                    'id': 1,
                    'value': 64,
                    'unit': 'bytes'
                },
                {
                    'name': 'txd/rxd',
                    'id': 2,
                    'value': 128,
                    'unit': 'descriptors'
                }
            ],
            'testcase': urljoin(settings.API_BASE_URL, 'testcases/1/')
        }
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'measurements/1/'),
            json=measurement)
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'measurements/2/'),
            json=measurement)

    def setup_mock_test_runs(self, m, fail=False):
        """Call `setup_mock_authenticated` before this."""
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'testruns/1/'),
            json={
                'url': urljoin(settings.API_BASE_URL, 'testruns/1/'),
                'timestamp': '2018-06-04T05:36:20Z',
                'log_output_file': None,
                'tarball': urljoin(settings.API_BASE_URL, 'tarballs/1/'),
                'results': [
                    {
                        'id': 1,
                        'result': 'PASS',
                        'difference': -0.185655863091204,
                        'expected_value': None,
                        'measurement': urljoin(settings.API_BASE_URL, 'measurements/1/'),
                        'result_class': 'success'
                    },
                    {
                        'id': 2,
                        'result': 'FAIL' if fail else 'PASS',
                        'difference': -0.664055231513893,
                        'expected_value': None,
                        'measurement': urljoin(settings.API_BASE_URL, 'measurements/2/'),
                        'result_class': 'success'
                    },
                ],
                'environment': urljoin(settings.API_BASE_URL, 'environments/1/'),
                'report_timestamp': None,
                'log_upload_file': None
            })
        ps_1 = {
            'url': urljoin(settings.API_BASE_URL, 'patchsets/1/'),
            'id': 1,
            'is_public': True,
            'apply_error': False,
            'tarballs': [
                urljoin(settings.API_BASE_URL, 'tarballs/1/')
            ],
            'status': 'Possible Regression' if fail else 'Pass',
            'status_class': 'danger' if fail else 'success',
            'status_tooltip': 'Possible Regression' if fail else 'Pass',
            'series_id': 1,
            'pw_series_url': urljoin(settings.PATCHWORKS_URL, 'series/1'),
            'completed_timestamp': '2018-07-20T00:00:00Z',
            'incomplete': 0,
            'passed': 0,
            'failed': 0,
            'build_error': False,
            'has_error': False
        }
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL,
                           'patchsets/?pw_is_active=true&without_series=false&ordering=-id&offset=0'),
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [ps_1]
            })
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'patchsets/1/'),
            json=ps_1)
        return ps_1

    def setup_mock_environment(self, m, **kwargs):
        """Create environment a mock environment

        Make sure to update the id if making multiple environments.
        Some environment URLs get autogenerated.
        """
        env = {
            'url': None,
            'id': 1,
            'inventory_id': 'IOL-ACME-00002',
            'owner': urljoin(settings.API_BASE_URL, 'group/3/'),
            'motherboard_make': 'Foo',
            'motherboard_model': 'Bar',
            'motherboard_serial': 'A',
            'cpu_socket_count': 1,
            'cpu_cores_per_socket': 1,
            'cpu_threads_per_core': 1,
            'ram_type': 'DDR',
            'ram_size': 1,
            'ram_channel_count': 1,
            'ram_frequency': 1,
            'nic_make': 'ACME',
            'nic_model': 'XL710',
            'nic_speed': 10000,
            'nic_dtscodename': 'Foo Bar 3',
            'nic_device_id': '04:00.0',
            'nic_device_bustype': 'pci',
            'nic_pmd': 'acme',
            'nic_firmware_source_id': '',
            'nic_firmware_version': '6.22',
            'kernel_cmdline': '',
            'kernel_name': 'linux',
            'kernel_version': 'A',
            'compiler_name': 'gcc',
            'compiler_version': 'A',
            'bios_version': 'A',
            'os_distro': 'Ubuntu 16.04',
            'measurements': [
                {
                    'url': urljoin(settings.API_BASE_URL, 'measurements/7/'),
                    'id': 7,
                    'name': 'throughput',
                    'unit': 'Mpps',
                    'higher_is_better': True,
                    'environment': None,
                    'parameters': [
                        {
                            'name': 'frame_size',
                            'id': 13,
                            'value': 64,
                            'unit': 'bytes'
                        },
                        {
                            'name': 'txd/rxd',
                            'id': 14,
                            'value': 128,
                            'unit': 'descriptors'
                        }
                    ],
                    'testcase': urljoin(settings.API_BASE_URL, '/testcases/1/')
                },
                {
                    'url': urljoin(settings.API_BASE_URL, '/measurements/8/'),
                    'id': 8,
                    'name': 'throughput',
                    'unit': 'Mpps',
                    'higher_is_better': True,
                    'environment': None,
                    'parameters': [
                        {
                            'name': 'frame_size',
                            'id': 15,
                            'value': 64,
                            'unit': 'bytes'
                        },
                        {
                            'name': 'txd/rxd',
                            'id': 16,
                            'value': 512,
                            'unit': 'descriptors'
                        }
                    ],
                    'testcase': urljoin(settings.API_BASE_URL, '/testcases/1/')
                },
                {
                    'url': urljoin(settings.API_BASE_URL, '/measurements/9/'),
                    'id': 9,
                    'name': 'throughput',
                    'unit': 'Mpps',
                    'higher_is_better': True,
                    'environment': None,
                    'parameters': [
                        {
                            'name': 'frame_size',
                            'id': 17,
                            'value': 64,
                            'unit': 'bytes'
                        },
                        {
                            'name': 'txd/rxd',
                            'id': 18,
                            'value': 2048,
                            'unit': 'descriptors'
                        }
                    ],
                    'testcase': urljoin(settings.API_BASE_URL, '/testcases/1/')
                }
            ],
            'contacts': [],
            'contact_policy': {
                'email_submitter': False,
                'email_recipients': False,
                'email_owner': False,
                'email_success': False,
                'email_list': 'pmacarth@iol.unh.edu'
            },
            'predecessor': None,
            'successor': None,
            'date': '2018-07-25T17:29:27Z',
            'live_since': None,
            'hardware_description': None
        }
        env.update(**kwargs)
        env_url = urljoin(settings.API_BASE_URL, f'environments/{env["id"]}/')
        env['url'] = env_url
        env['measurements'][0]['environment'] = env_url
        env['measurements'][1]['environment'] = env_url
        env['measurements'][2]['environment'] = env_url
        m.register_uri(
            'GET',
            urljoin(settings.API_BASE_URL, f'environments/{env["id"]}/'),
            json=env)
        return env

    def setup_mock_active(self, m, environments):
        """Set up which environments is considered active."""
        m.register_uri(
            'GET', urljoin(settings.API_BASE_URL, 'environments/?active=true'),
            json={
                'count': len(environments),
                'next': None,
                'previous': None,
                'results': environments
            })


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

    def test_anon_active_patchset(self, m):
        """Verify that an active patch is shown in the anonymous view."""
        self.setup_mock_anonymous(m)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchsets'][0]
        self.assertEqual(ps['id'], 1)
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(ps['submitter'], 'Thomas Monjalon')
        self.assertEqual(ps['status'], 'Pass')
        self.assertEqual(ps['status_class'], 'success')
        self.assertEqual(ps['status_tooltip'], 'Pass')

    def test_auth_active_patchset(self, m):
        """Verify that patchsets are shown properly in authenticated view."""
        self.setup_mock_authenticated(m)
        env = self.setup_mock_environment(m)
        self.setup_mock_active(m, [env])
        self.setup_mock_test_runs(m)

        response = self.client.post(
            reverse('login'),
            dict(username='acmevendor', password='P@$$w0rd'), follow=True)
        self.assertTrue(response.context['user'].is_active)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchsets'][0]
        self.assertEqual(ps['id'], 1)
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(ps['submitter'],
                         'Thomas Monjalon <thomas@monjalon.net>')
        self.assertEqual(ps['status'], 'Pass')
        self.assertEqual(ps['status_class'], 'success')
        self.assertEqual(ps['status_tooltip'], 'Pass')


@requests_mock.Mocker()
class DetailViewTests(BaseTestCase):
    """Test the detail view."""

    def test_anon_load(self, m):
        """Test that the anonymous page loads."""
        ps = self.setup_mock_anonymous(m)

        response = self.client.get(reverse('dashboard-detail',
                                           args=(ps['id'],)))

        self.assertEqual(response.status_code, 200)
        ps = response.context['patchset']
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(len(ps['patches']), 1)
        self.assertEqual(ps['status'], 'Pass')
        self.assertEqual(len(response.context['environments'].items()), 0)

    def test_auth_fail(self, m):
        """Test a result with a failing result."""
        self.setup_mock_authenticated(m)
        env = self.setup_mock_environment(m)
        self.setup_mock_active(m, [env])
        ps = self.setup_mock_test_runs(m, fail=True)

        response = self.client.get(reverse('dashboard-detail',
                                           args=(ps['id'],)),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchset']
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(len(ps['patches']), 1)
        self.assertEqual(ps['status'], 'Possible Regression')
        env = response.context['environments'][
            urljoin(settings.API_BASE_URL, reverse('environment-detail',
                                                   args=(env['id'],)))]
        self.assertEqual(len(env['runs'][0]['results']), 2)
        self.assertEqual(env['id'], env['id'])
        self.assertEqual(env['nic_model'], 'XL710')
        self.assertEqual(env['runs'][0]['failure_count'], 1)
        self.assertEqual(env['runs'][0]['results'][0]['result'], 'PASS')
        self.assertEqual(env['runs'][0]['results'][1]['result'], 'FAIL')
        self.assertAlmostEqual(env['runs'][0]['results'][0]['difference'],
                               -0.185655, places=5)
        self.assertAlmostEqual(env['runs'][0]['results'][1]['difference'],
                               -0.664055, places=5)

    def test_auth_load(self, m):
        """Test that the authenticated page loads."""
        self.setup_mock_authenticated(m)
        env = self.setup_mock_environment(m)
        self.setup_mock_active(m, [env])
        ps = self.setup_mock_test_runs(m)

        response = self.client.get(reverse('dashboard-detail',
                                           args=(ps['id'],)),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchset']
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(len(ps['patches']), 1)
        self.assertEqual(ps['status'], 'Pass')
        env = response.context['environments'][
            urljoin(settings.API_BASE_URL, reverse('environment-detail',
                                                   args=(env['id'],)))]
        self.assertEqual(len(env['runs'][0]['results']), 2)
        self.assertEqual(env['id'], env['id'])
        self.assertEqual(env['nic_model'], 'XL710')
        self.assertEqual(env['runs'][0]['failure_count'], 0)
        self.assertEqual(env['runs'][0]['results'][0]['result'], 'PASS')
        self.assertAlmostEqual(env['runs'][0]['results'][0]['difference'],
                               -0.185655, places=5)
        self.assertAlmostEqual(env['runs'][0]['results'][1]['difference'],
                               -0.664055, places=5)

    def test_auth_successor(self, m):
        """Verify that runs dictionary uses successor environment."""
        self.setup_mock_authenticated(m)
        self.setup_mock_environment(
            m, successor=urljoin(settings.API_BASE_URL, 'environments/2/'))
        cloned_env = self.setup_mock_environment(
            m, id=2,
            predecessor=urljoin(settings.API_BASE_URL, 'environments/1/'))
        ps = self.setup_mock_test_runs(m)
        self.setup_mock_active(m, [cloned_env])

        response = self.client.get(reverse('dashboard-detail',
                                           args=(ps['id'],)),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        ps = response.context['patchset']
        self.assertEqual(ps['patchwork_range_str'], '40574')
        self.assertEqual(len(ps['patches']), 1)
        self.assertEqual(ps['status'], 'Pass')
        env = response.context['environments'][
            urljoin(settings.API_BASE_URL, reverse('environment-detail',
                                                   args=(cloned_env['id'],)))]
        self.assertEqual(len(env['runs'][0]['results']), 2)
        self.assertEqual(env['id'], cloned_env['id'])
        self.assertEqual(env['nic_model'], 'XL710')
        self.assertEqual(env['runs'][0]['failure_count'], 0)
        self.assertEqual(env['runs'][0]['results'][0]['result'], 'PASS')
        self.assertAlmostEqual(env['runs'][0]['results'][0]['difference'],
                               -0.185655, places=5)
        self.assertAlmostEqual(env['runs'][0]['results'][1]['difference'],
                               -0.664055, places=5)


@requests_mock.Mocker()
class AboutViewTests(BaseTestCase):
    """Test the about view."""

    def test_anon_active_legend(self, m):
        """Verify that the status legend is populated properly in context."""
        self.setup_mock_anonymous(m)

        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        legend = response.context['statuses']
        self.assertEqual(legend[0]['name'], 'Pass')
        self.assertEqual(legend[0]['class'], 'success')
        self.assertEqual(legend[0]['tooltip'], 'Pass')


class SubscriptionsViewTests(BaseTestCase):
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
        response = self.client.get(reverse('subscriptions'))
        self.assertEqual(response.status_code, 302)

    def test_no_env(self):
        """Test the template and returns an empty list."""
        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('subscriptions'))

        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['env_sub_pairs'], [])

    def test_with_env(self):
        """Test the template and return a list."""
        env = create_test_environment(owner=self.grp1)

        with self.settings(API_BASE_URL=self.live_server_url):
            response = self.client.post(reverse('login'),
                dict(username=self.user1.username, password='AbCdEfGh'), follow=True)
            self.assertTrue(response.context['user'].is_active)

            response = self.client.get(reverse('subscriptions'))

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

            response = self.client.get(reverse('subscriptions'))

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

            response = self.client.get(reverse('subscriptions'))

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

            response = self.client.get(reverse('subscriptions'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['env_sub_pairs'][0]['environment']['id'], env.id)
        self.assertEqual(response.context['env_sub_pairs'][0]['subscription'], None)


class PaginationTests(test.TestCase):
    """Test the pagination.

    These are somewhat minimal since we are utiling the Django REST methods.
    """

    def test_valid_case(self):
        """Test that nothing breaks under normal circumstances."""
        context = {}
        paginate_rest(parse_page(5), context, 20)
        self.assertEqual(context['next_url'], '?page=6')
        self.assertEqual(context['previous_url'], '?page=4')

        context = {}
        paginate_rest(parse_page(10), context, 20)
        self.assertIsNone(context['next_url'])
        self.assertEqual(context['previous_url'], '?page=9')

        context = {}
        paginate_rest(parse_page(1), context, 20)
        self.assertEqual(context['next_url'], '?page=2')
        self.assertIsNone(context['previous_url'])

        context = {}
        paginate_rest(parse_page(1), context, 2)
        self.assertIsNone(context['next_url'])
        self.assertIsNone(context['previous_url'])

        # check ceil properly
        context = {}
        paginate_rest(parse_page(1), context, 3)
        self.assertEqual(context['next_url'], '?page=2')
        self.assertIsNone(context['previous_url'])

    def test_zero_index(self):
        """Test that zero gets converted to page 1."""
        context = {}
        paginate_rest(parse_page(0), context, 20)
        self.assertEqual(context['next_url'], '?page=2')

        context = {}
        paginate_rest(parse_page(0), context, 2)
        self.assertIsNone(context['next_url'])
        self.assertIsNone(context['previous_url'])

    def test_negatives(self):
        """Test that wrapping occurs."""
        context = {}
        paginate_rest(parse_page(-1), context, 20)
        self.assertEqual(context['previous_url'], '?page=9')

        context = {}
        paginate_rest(parse_page(-11), context, 20)
        self.assertEqual(context['previous_url'], '?page=9')

        context = {}
        paginate_rest(parse_page(-1), context, 2)
        self.assertIsNone(context['next_url'])
        self.assertIsNone(context['previous_url'])

        context = {}
        paginate_rest(parse_page(-11), context, 2)
        self.assertIsNone(context['next_url'])
        self.assertIsNone(context['previous_url'])

    def test_pages_greater_than_page(self):
        """Test that we get a 404 if page > pages."""
        with self.assertRaises(Http404):
            paginate_rest(parse_page(11), {}, 20)

        with self.assertRaises(Http404):
            paginate_rest(parse_page(2), {}, 2)


class ParseIPAChangePasswordTests(TestCase):
    """Test password change parser from IPA."""

    def setUp(self):
        """Set up parser."""
        super().setUp()
        self.parser = ParseIPAChangePassword()

    def test_successful(self):
        """Test a successful password change."""
        html = """<html>
<head>
<title>200 Success</title>
</head>
<body>
<h1>Password change successful</h1>
<p>
<strong>Password was changed.</strong>
</p>
</body>
</html>"""
        self.parser.feed(html)
        self.assertEqual(self.parser.header, 'Password change successful')
        self.assertEqual(self.parser.message, 'Password was changed.')

    def test_bad_password(self):
        """Test a wrong password change."""
        html = """<html>
<head>
<title>200 Success</title>
</head>
<body>
<h1>Password change rejected</h1>
<p>
<strong>The old password or username is not correct.</strong>
</p>
</body>
</html>"""
        self.parser.feed(html)
        self.assertEqual(self.parser.header, 'Password change rejected')
        self.assertEqual(self.parser.message, 'The old password or username is not correct.')
