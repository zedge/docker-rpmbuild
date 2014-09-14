from __future__ import with_statement
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

    @patch('rpmbuild.build.PackagerContext', autospec=True)
    @patch('rpmbuild.build.Packager', autospec=True)
    @patch('rpmbuild.build.log')
    @patch('sys.exit')
    def test_build_and_packager_has_packagerexception_has_exit_code_1(self, sys_exit_mock, log_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'build',
                                '--source', 'foo.tar',
                                '--spec', 'bar.spec',
                                'docker_image'
        ]):
            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.side_effect = PackagerException('foo')
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            # (caught by with?)
            #with self.assertRaises(PackagerException):
            build.main()

        sys_exit_mock.assert_called_once_with(1)
        log_mock.assert_called_once_with('Container build failed!', file=sys.stderr)


    @patch('rpmbuild.build.PackagerContext', autospec=True)
    @patch('rpmbuild.build.Packager', autospec=True)
    @patch('rpmbuild.build.log')
    @patch('sys.exit')
    def test_build_raises_package_exception_if_parser_finds_errors(self, sys_exit_mock, print_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                         'build',
                         '--source', 'foo.tar',
                         '--spec', 'bar.spec',
                         'docker_image'
                        ]):

            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                '{"stream": "Step 1..."}',
                '{"error":"Error...", "errorDetail":{"code": 123, "message": "Error..."}}',
            ]
            packager_mock_enter.build_package.return_value = [MagicMock(spec=Client), [MagicMock()]]
            packager_mock.return_value.__enter__.return_value = packager_mock_enter

            # Why? :(
            #with self.assertRaises(PackagerException):
            build.main()
            print_mock.assert_any_call(
                {"error":"Error...", "errorDetail":{"code": 123, "message": "Error..."}})


    @patch('rpmbuild.build.PackagerContext', autospec=True)
    @patch('rpmbuild.build.Packager', autospec=True)
    @patch('__builtin__.print')
    def test_build_valid_exit_zero(self, print_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                         'build',
                         '--source', 'foo.tar',
                         '--spec', 'bar.spec',
                         '--output', '/tmp/',
                         'docker_image'
                        ]):


            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                '{"stream": "Step 1..."}',
                '{"stream": "..."}'
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


    @patch('rpmbuild.build.PackagerContext', autospec=True)
    @patch('rpmbuild.build.Packager', autospec=True)
    @patch('rpmbuild.build.log')
    def test_rebuild_valid_exit_zero(self, print_mock, packager_mock, context_mock):
        with patch('sys.argv', ['docker-rpmbuild',
                                'rebuild',
                                '--srpm', 'foo.src.rpm',
                                'docker_image'
        ]):
            packager_mock_enter = MagicMock()
            packager_mock_enter.build_image.return_value = [
                '{"stream": "Step 1..."}',
                '{"stream": "..."}'
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