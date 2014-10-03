from __future__ import with_statement, unicode_literals
from collections import defaultdict

try:
    from ConfigParser import ConfigParser
    from StringIO import StringIO
except ImportError:
    from configparser import ConfigParser
    from io import StringIO

from docker import Client
from docopt import DocoptExit

from mock import call, MagicMock, patch
import sys
from unittest2 import TestCase
from rpmbuild import build, PackagerException


class BuildTest(TestCase):

    def test_no_main_targets_return_help_text(self):
        with self.assertRaises(DocoptExit):
            build.main()

    def test_build_with_no_image_returns_help_text(self):
        with patch('sys.argv', ['build']):
            with self.assertRaises(DocoptExit):
                build.main()

    @patch('rpmbuild.build.PackagerContext')
    @patch('rpmbuild.build.Packager')
    @patch('rpmbuild.build.get_parsed_config')
    @patch('rpmbuild.build.log')
    @patch('sys.exit')
    def test_build_and_packager_has_packagerexception_has_exit_code_1(
            self, sys_exit_mock, log_mock, config_mock, packager_mock,
            context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'build',
                                '--source', 'foo.tar',
                                '--spec', 'bar.spec',
                                'docker_image'
        ]):

            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.side_effect = PackagerException('foo')
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            build.main()

        sys_exit_mock.assert_called_once_with(1)
        log_mock.assert_called_once_with('Container build failed!', file=sys.stderr)


    @patch('rpmbuild.build.PackagerContext')
    @patch('rpmbuild.build.Packager')
    @patch('rpmbuild.build.get_parsed_config')
    @patch('rpmbuild.build.log')
    @patch('sys.exit')
    def test_build_raises_package_exception_if_parser_finds_errors(
            self, sys_exit_mock, print_mock, config_mock, packager_mock,
            context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'build',
                                '--source', 'foo.tar',
                                '--spec', 'bar.spec',
                                'docker_image'
        ]):
            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                b'{"stream": "Step 1..."}',
                b'{"error":"Error...", "errorDetail":{"code": 123, "message": "Error..."}}',
            ]
            packager_mock_enter.build_package.return_value = [MagicMock(spec=Client), [MagicMock()]]
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            build.main()
            print_mock.assert_any_call(
                {"error": "Error...", "errorDetail": {"code": 123, "message": "Error..."}})


    @patch('rpmbuild.build.PackagerContext')
    @patch('rpmbuild.build.Packager')
    @patch('rpmbuild.build.get_parsed_config')
    @patch('rpmbuild.build.log')
    def test_build_valid_exit_zero(self, print_mock, config_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'build',
                                '--source', 'foo.tar',
                                '--spec', 'bar.spec',
                                '--output', '/tmp/',
                                'docker_image'
        ]):
            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                b'{"stream": "Step 1..."}',
                b'{"stream": "..."}'
            ]
            packager_mock_enter.export_package.return_value = ['/tmp/a_build.rpm']
            packager_mock_enter.build_package.return_value = [MagicMock(spec=Client), [MagicMock()]]
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            build.main()

            packager_mock_enter.export_package.assert_called_with('/tmp/')

            calls_on_packager = [
                call.build_image(),
                call.build_package(),
                call.export_package('/tmp/'),
            ]
            packager_mock_enter.assert_has_calls(calls_on_packager)


    @patch('rpmbuild.build.PackagerContext')
    @patch('rpmbuild.build.Packager')
    @patch('rpmbuild.build.get_parsed_config')
    @patch('rpmbuild.build.log')
    def test_rebuild_valid_exit_zero(self, print_mock, config_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'rebuild',
                                '--srpm', 'foo.src.rpm',
                                'docker_image'
        ]):
            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                b'{"stream": "Step 1..."}',
                b'{"stream": "..."}'
            ]
            packager_mock_enter.export_package.return_value = ['/rpmbuild/a_build.rpm']
            packager_mock_enter.build_package.return_value = [MagicMock(spec=Client), [MagicMock()]]
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            build.main()

            packager_mock_enter.export_package.assert_called_with('.')

            calls_on_packager = [
                call.build_image(),
                call.build_package(),
                call.export_package('.'),
            ]
            packager_mock_enter.assert_has_calls(calls_on_packager)

    @patch('rpmbuild.build.Packager')
    @patch('os.path.exists', return_value=True)
    def test_build_with_only_values_from_config_provides_valid_package_context(
            self, exists_mock, packager_mock):
        config = {
            'image': 'debian',
            'define': ['_sysconfdir /etc/foo', '_binddir /bin'],
            'spec': 'super_advanced.spec',
            'macrofile': ['silly macros.spec', 'macro2.spec'],
            'retrieve': True,
            'source': ['source-foo', 'source-bar', 'keke-source', 'docker-source'],
            'sources_dir': 'super_directory_with_sources'
        }
        args = {
            '--config': '/etc/config.ini',
            '--define': [],
            '--docker-base_url': None,
            '--docker-timeout': None,
            '--docker-version': None,
            '--output': None,
            '--retrieve': False,
            '--source': [],
            '--sources-dir': None,
            '--macrofile': None,
            '--spec': None,
            '--srpm': None,
            '<image>': None,
            'build': True,
            'rebuild': False
        }

        context = build.get_context(args, config)
        self.assertEqual(context.image, 'debian')
        self.assertEqual(context.defines, ['_sysconfdir /etc/foo', '_binddir /bin'])
        self.assertEqual(context.spec, 'super_advanced.spec')
        self.assertEqual(context.macrofiles, ['silly macros.spec', 'macro2.spec'])
        self.assertEqual(context.retrieve, True)
        self.assertEqual(context.sources, ['source-foo', 'source-bar', 'keke-source', 'docker-source'])
        self.assertEqual(context.sources_dir, 'super_directory_with_sources')

    def test_get_context_with_missing_docopt_options_raises_docoptexit(self):
        with self.assertRaises(DocoptExit):
            build.get_context({'build': False, 'rebuild': False}, defaultdict(None, {}))


    def mock_it(self, builtin_name):
        """ https://wiki.python.org/moin/PortingToPy3k/BilingualQuickRef """
        name = ('builtins.%s' if sys.version_info >= (3,) else '__builtin__.%s') % builtin_name
        return patch(name)

    @patch('sys.stderr')
    def test_print_with_file_include_filehandle_in_print_statement(self, stderr_mock):
        with self.mock_it('print') as print_mock:
            build.log('foo', sys.stderr)
            print_mock.assert_called_with('foo', stderr_mock)


    def test_print_without_file(self):
        with self.mock_it('print') as print_mock:
            build.log('bar')
            print_mock.assert_called_with('bar')
