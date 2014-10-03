from __future__ import unicode_literals

try:
    from ConfigParser import ConfigParser
    from StringIO import StringIO
except ImportError:
    from configparser import ConfigParser
    from io import StringIO

from collections import defaultdict
import unittest2 as unittest
from mock import mock_open, patch
from rpmbuild.config import _read_config, _read_section, get_docker_config, DEFAULT_TIMEOUT, get_parsed_config


class ConfigTestCase(unittest.TestCase):
    """Tests for config.py"""

    def setUp(self):
        self.config_file = '/etc/docker.config'

        self.config_without_docker_section = """[foo]
missing=docker-section
        """
        self.config_with_none_values = """[docker]
base_url=
version=1.11
"""
        self.config_containg_all_attributes_valid = """[docker]
base_url=tcp://127.0.0.1:4242
timeout=42
version=1.11
"""
        self.all_configs = [
            self.config_containg_all_attributes_valid,
            self.config_without_docker_section,
            self.config_with_none_values
        ]

        self.docopt_with_only_config_file_without_timeout = {
            '--config': self.config_file,
            '--define': [],
            '--docker-base_url': None,
            '--docker-timeout': None,
            '--docker-version': None,
            '--output': '.',
            '--retrieve': True,
            '--source': [],
            '--sources-dir': 'SOURCES',
            '--spec': 'SPECS/foo.spec',
            '--srpm': None,
            '<image>': 'docker.example.net:5000/centos:7',
            'build': True,
            'rebuild': False
        }

    def test_read_config_is_defaultdict(self):
        for config in self.all_configs:
            file_config_mock = mock_open(StringIO(config))
            with patch('rpmbuild.build.open', file_config_mock, create=True):
                config_dict = _read_config(file_config_mock)
                self.assertIsInstance(
                    config_dict,
                    defaultdict,
                    '{0} file returns non defaultdict!'.format(config))

    def test_read_config_returns_blank_config_when_missing_section(self):
        file_config_mock = mock_open(StringIO(self.config_without_docker_section))
        with patch('rpmbuild.build.open', file_config_mock, create=True):
            config = _read_config(file_config_mock)
            self.assertDictEqual(config, {}, 'config should be empty')

    def test_read_config_removes_none_values_from_config_dict(self):
        file_config_mock = mock_open(StringIO(self.config_with_none_values))
        with patch('rpmbuild.build.open', file_config_mock, create=True):
            config = _read_config(file_config_mock)
            self.assertDictEqual(dict(config), {'version': '1.11'},
                             'should strip away base_url')

    def test_read_config_timeout_is_int(self):
        file_config_mock = mock_open(StringIO(self.config_containg_all_attributes_valid))
        with patch('rpmbuild.build.open', file_config_mock, create=True):
            config = _read_config(file_config_mock)
            self.assertEqual(config.get('timeout'), 42,
                             'Should contain the integer 42 in timeout')


    def test_get_docker_config_is_type_defaultdict(self):
        config_from_file = defaultdict(None, {
                'timeout': 42,
                'version': '0.11'
            })

        config = get_docker_config(self.docopt_with_only_config_file_without_timeout, config_from_file)

        self.assertIsInstance(
            config,
            defaultdict,
            '{0} file returns non defaultdict!'.format(config))

    def test_get_docker_config_insert_internal_default_if_no_timeout_is_given_either_as_docopt_argument_or_config(self):
        config_from_file = defaultdict(None, {
                'version': '0.11'
            })

        config = get_docker_config(self.docopt_with_only_config_file_without_timeout, config_from_file)
        self.assertEqual(config.get('timeout'), int(DEFAULT_TIMEOUT))


    def test_get_docker_config_gets_doctopt_timeout_when_provided_and_no_config_given(self):
        docopt_with_timeout_and_no_config = {
            '--config': None,
            '--define': [],
            '--docker-base_url': None,
            '--docker-timeout': 44,
            '--docker-version': None,
            '--output': '.',
            '--retrieve': True,
            '--source': [],
            '--sources-dir': 'SOURCES',
            '--spec': 'SPECS/foo.spec',
            '--srpm': None,
            '<image>': 'docker.example.net:5000/centos:7',
            'build': True,
            'rebuild': False
        }


        config_from_file = defaultdict(None, {
                'version': '0.11'
            })

        config = get_docker_config(docopt_with_timeout_and_no_config, config_from_file)
        self.assertEqual(config.get('timeout'), 44)

    def test_get_docker_config_gets_overriden_timeout_provided_in_docopts_over_config_files_timeout(self):
        docopt_with_timeout_and_with_config = {
            '--config': '/tmp/foo',
            '--define': [],
            '--docker-base_url': None,
            '--docker-timeout': 48,
            '--docker-version': None,
            '--output': '.',
            '--retrieve': True,
            '--source': [],
            '--sources-dir': 'SOURCES',
            '--spec': 'SPECS/foo.spec',
            '--srpm': None,
            '<image>': 'docker.example.net:5000/centos:7',
            'build': True,
            'rebuild': False
        }

        config_from_file = defaultdict(None, {
                'timeout': 41,
                'version': '0.11'
        })

        config = get_docker_config(docopt_with_timeout_and_with_config, config_from_file)
        self.assertEqual(config.get('timeout'), 48)

    def test_get_docker_config_has_no_timeout_nor_timeout_in_docopts_returns_internal_default_value(self):
        docopt_with_timeout_and_with_config = {
            '--config': '/tmp/foo',
            '--docker-base_url': None,
            '--docker-version': None,
            '--docker-timeout': None,
        }
        config_from_file = defaultdict(None, {
                'version': '0.11'
        })

        config = get_docker_config(docopt_with_timeout_and_with_config, config_from_file)
        self.assertEqual(config.get('timeout'), int(DEFAULT_TIMEOUT))


    def setup_multiget_two_sources(self):
        self.raw_config = """[build]
source=foo
       bar
"""
    def setup_multiget_four_sources(self):
        self.raw_config = """[build]
source=foo
       bar
        keke
          docker
"""


    def test_read_section_multi_get_returns_values_in_list(self):
        self.setup_multiget_two_sources()
        config = ConfigParser()
        config.readfp(StringIO(self.raw_config))

        config_dict = _read_section('build', {'source': 'multi-get'}, config)
        self.assertIsInstance(config_dict.get('source'), list)

    def test_read_section_multi_get_contains_correct_number_of_items(self):
        self.setup_multiget_two_sources()
        config = ConfigParser()

        config.readfp(StringIO(self.raw_config))
        config_dict = _read_section('build', {'source': 'multi-get'}, config)
        self.assertEqual(2, len(config_dict.get('source')))

        self.setup_multiget_four_sources()
        config = ConfigParser()
        config.readfp(StringIO(self.raw_config))
        config_dict = _read_section('build', {'source': 'multi-get'}, config)
        self.assertEqual(4, len(config_dict.get('source')))
        self.assertEqual('keke', config_dict.get('source')[-2])

    @patch('rpmbuild.config.os.path.exists', return_value=True)
    def test_get_parsed_config_reads_config_file_with_spec_goal(self, os_exists_mock):
        raw_config = """[build]
image=debian
define=_sysconfdir /etc/foo
       _binddir /bin
spec=super_advanced.spec
macrofile=silly macros.spec
          macro2.spec
retrieve=True
source=source-foo
       source-bar
       keke-source
       docker-source
sources_dir=super_directory_with_sources
"""

        docopt_args = {
            '--spec': 'foo.spec',
            '--srpm': None,
            'build': True,
        }

        with patch('rpmbuild.config.open', mock_open(), create=True) as m:
            m.return_value.__enter__.return_value = StringIO(raw_config)

            config = get_parsed_config(docopt_args)
            self.assertEqual('super_directory_with_sources', config.get('sources_dir'))
            self.assertEqual(4, len(config.get('source')))

    @patch('rpmbuild.config.os.path.exists', return_value=True)
    def test_get_parsed_config_reads_config_file_with_srpm_goal(self, os_exists_mock):
        raw_config = """[build]
image=debian
define=_sysconfdir /etc/foo
       _binddir /bin
spec=super_advanced.spec
macrofile=silly macros.spec
          macro2.spec
retrieve=True
source=source-foo
       source-bar
       keke-source
       docker-source
sources_dir=super_directory_with_sources
"""

        docopt_args = {
            '--spec': None,
            '--srpm': 'bar.srpm',
            'build': True,
        }

        with patch('rpmbuild.config.open', mock_open(), create=True) as m:
            m.return_value.__enter__.return_value = StringIO(raw_config)

            config = get_parsed_config(docopt_args)
            self.assertEqual('super_directory_with_sources', config.get('sources_dir'))
            self.assertEqual(4, len(config.get('source')))


    @patch('rpmbuild.config.os.path.exists', return_value=False)
    def test_get_parsed_config_returns_empty_defaultdict_if_config_not_found(self, os_exists_mock):
        docopt_args = {
            '--spec': 'foo.spec',
            '--srpm': None,
            'build': True,
        }
        config = get_parsed_config(docopt_args)
        self.assertIsInstance(config, defaultdict)
        self.assertEqual(0, len(config.keys()))


    def test_get_parsed_config_returns_empty_defaultdict_if_spec_or_srpm_goals_not_set(self):
        docopt_args = {
            '--spec': None,
            '--srpm': None,
            'build': True,
        }

        config = get_parsed_config(docopt_args)
        self.assertIsInstance(config, defaultdict)
        self.assertEqual(0, len(config.keys()))