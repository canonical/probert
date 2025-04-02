import contextlib
import logging
import os
import pathlib
import tempfile
import textwrap
import unittest
from unittest.mock import call

from probert import utils
from probert.tests.helpers import random_string


class ProbertTestUtils(unittest.TestCase):
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
        expected_path = pathlib.Path(f'/sys/class/block/{devname}/size')
        expected_bytes = 10737418240
        content = '20971520'

        with unittest.mock.patch("probert.utils.Path.read_text",
                                 autospec=True,
                                 return_value=content) as m_read_text:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            m_read_text.assert_called_once()
            self.assertEqual([call(expected_path)], m_read_text.call_args_list)

    def test_utils_read_sys_block_size_bytes_strips_value(self):
        devname = random_string()
        expected_path = pathlib.Path(f'/sys/class/block/{devname}/size')
        expected_bytes = 10737418240
        content = ' 20971520 \n '

        with unittest.mock.patch("probert.utils.Path.read_text",
                                 autospec=True,
                                 return_value=content) as m_read_text:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            m_read_text.assert_called_once()
            self.assertEqual([call(expected_path)], m_read_text.call_args_list)

    def test_utils_read_sys_devpath_size_bytes_strips_value(self):
        devpath = """\
/devices/pci0000:00/0000:00:1d.0/0000:03:00.0/nvme/nvme0/nvme0n1/nvme0n1p3"""
        expected_path = pathlib.Path(f'/sys{devpath}/size')
        expected_bytes = 10737418240
        content = ' 20971520 \n '

        with unittest.mock.patch("probert.utils.Path.read_text",
                                 autospec=True,
                                 return_value=content) as m_read_text:
            result = utils.read_sys_devpath_size_bytes(devpath)
            self.assertEqual(expected_bytes, result)
            self.assertEqual([call(expected_path)], m_read_text.call_args_list)

    def test_utils_read_sys_devpath_size_bytes__inexistent_nologging(self):
        with self.assertRaises(FileNotFoundError):
            utils.read_sys_devpath_size_bytes("/devices/that/does/not/exist")

    def test_utils_read_sys_devpath_size_bytes__existent_directory(self):
        with self.assertRaises(FileNotFoundError) as cm_exc:
            # /sys/devices/<size> should not exist but /sys/devices should
            with self.assertLogs("probert.utils", level="WARNING") as cm_log:
                utils.read_sys_devpath_size_bytes("/devices", log_inexistent=True)
        self.assertEqual("%s contains %s", cm_log.records[0].msg)
        path, child_paths = cm_log.records[0].args
        self.assertEqual(pathlib.Path("/sys/devices"), path)
        for child in child_paths:
            self.assertIsInstance(child, pathlib.Path)
        self.assertIsNone(cm_exc.exception.__context__)

    def test_utils_read_sys_devpath_size_bytes__inexistent_directory(self):
        with self.assertRaises(FileNotFoundError) as cm_exc:
            utils.read_sys_devpath_size_bytes("/devices/that/does/not/exist/nvme0n1p3",
                                              log_inexistent=True)
        self.assertIsInstance(cm_exc.exception.__context__, FileNotFoundError)


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


class ProbertTestRun(unittest.TestCase):
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
