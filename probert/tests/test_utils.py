import contextlib
import logging
from mock import call
import os
import tempfile
import testtools
import textwrap
import unittest

from probert import utils
from probert.tests.helpers import random_string, simple_mocked_open


class ProbertTestUtils(testtools.TestCase):
    def setUp(self):
        super(ProbertTestUtils, self).setUp()

    def test_utils_dict_merge(self):
        r1 = {'relations': ['m1', 'x1']}
        r2 = {'relations': ['m2', 'x2']}
        combined = {'relations': ['m1', 'm2', 'x1', 'x2']}
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(sorted(combined['relations']),
                         sorted(test_result['relations']))

    def test_utils_dict_merge_lists(self):
        r1 = ['m1', 'x1']
        r2 = ['m2', 'x2']
        combined = ['m1', 'm2', 'x1', 'x2']
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(sorted(combined), sorted(test_result))

    def test_utils_dict_merge_dicts(self):
        r1 = {'storage': {'/dev/sda': {'DEVTYPE': 'disk'}}}
        r2 = {'storage': {'/dev/sda': {'ID_MODEL': 'AWESOME'}}}
        combined = {
            'storage': {
                '/dev/sda': {
                    'DEVTYPE': 'disk',
                    'ID_MODEL': 'AWESOME',
                }
            }
        }
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(sorted(combined), sorted(test_result))

    def test_utils_read_sys_block_size_bytes(self):
        devname = random_string()
        expected_fname = '/sys/class/block/%s/size' % devname
        expected_bytes = 10737418240
        content = '20971520'
        with simple_mocked_open(content=content) as m_open:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            self.assertEqual([call(expected_fname)], m_open.call_args_list)

    def test_utils_read_sys_block_size_bytes_strips_value(self):
        devname = random_string()
        expected_fname = '/sys/class/block/%s/size' % devname
        expected_bytes = 10737418240
        content = ' 20971520 \n '
        with simple_mocked_open(content=content) as m_open:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            self.assertEqual([call(expected_fname)], m_open.call_args_list)


@contextlib.contextmanager
def create_script(content):
    try:
        script = None
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fp:
            fp.write(textwrap.dedent(content))
            script = fp.name
        os.chmod(script, 0o755)
        yield script
    finally:
        if script:
            os.remove(script)


class ProbertTestRun(testtools.TestCase):
    leader = 'DEBUG:probert.utils:'

    def test_run_success_no_output(self):
        content = '''\
            #!/bin/sh
            exit 0
        '''
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, 'a', 'b', 'c'])
            expected = [self.leader + line for line in (
                f'Command `{script} a b c` exited with result: 0',
                '<empty stdout>',
                '<empty stderr>',
                '--------------------------------------------------',
            )]
            self.assertEqual('', actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_success_no_stderr(self):
        content = '''\
            #!/bin/sh
            echo "Line 1"
            echo "Line 2"
            exit 0
        '''
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, 'a', 'b', 'c'])
            expected = [self.leader + line for line in (
                f'Command `{script} a b c` exited with result: 0',
                'stdout: ------------------------------------------',
                'Line 1',
                'Line 2',
                '<empty stderr>',
                '--------------------------------------------------',
            )]
            self.assertEqual('Line 1\nLine 2\n', actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_empty_output(self):
        content = '''\
            #!/bin/sh
            echo
            exit 0
        '''
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, 'a', 'b', 'c'])
            expected = [self.leader + line for line in (
                f'Command `{script} a b c` exited with result: 0',
                'stdout: ------------------------------------------',
                '',
                '<empty stderr>',
                '--------------------------------------------------',
            )]
            self.assertEqual('\n', actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_success_with_stderr(self):
        content = '''\
            #!/bin/sh
            echo "Success message"
            echo "Diagnostic info" 1>&2
            exit 0
        '''
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, 'a', 'b', 'c'])
            expected = [self.leader + line for line in (
                f'Command `{script} a b c` exited with result: 0',
                'stdout: ------------------------------------------',
                'Success message',
                'stderr: ------------------------------------------',
                'Diagnostic info',
                '--------------------------------------------------',
            )]
            self.assertEqual('Success message\n', actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_failure(self):
        content = '''\
            #!/bin/bash
            echo "Bad output"
            echo "You did it wrong" 1>&2
            exit 7
        '''
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script])
            expected = [self.leader + line for line in (
                f'Command `{script}` exited with result: 7',
                'stdout: ------------------------------------------',
                'Bad output',
                'stderr: ------------------------------------------',
                'You did it wrong',
                '--------------------------------------------------',
            )]
            self.assertIsNone(actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_nonunicode_out(self):
        with self.assertLogs('probert.utils', level=logging.DEBUG) as m_logs:
            with unittest.mock.patch('subprocess.run') as m_run:
                m_run.return_value = unittest.mock.Mock()
                m_run.return_value.returncode = 0
                m_run.return_value.stdout = b'r\xe9serv\xe9e'
                m_run.return_value.stderr = b''
                actual = utils.run(['cmd'])
        expected = [self.leader + line for line in (
            'Command `cmd` exited with result: 0',
            'UnicodeDecodeError on stdout: '
            "'utf-8' codec can't decode byte 0xe9 in position 1: "
            'invalid continuation byte',
            'stdout: ------------------------------------------',
            'r\\xe9serv\\xe9e',
            '<empty stderr>',
            '--------------------------------------------------',
        )]
        self.assertIsNone(actual)
        self.assertEqual(expected, m_logs.output)
