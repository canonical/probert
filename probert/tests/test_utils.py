import asyncio
import contextlib
import logging
import os
import signal
import tempfile
import textwrap
import unittest
from unittest.mock import call, patch

from probert import utils
from probert.tests.helpers import random_string, simple_mocked_open


class ProbertTestUtils(unittest.TestCase):
    def setUp(self):
        super(ProbertTestUtils, self).setUp()

    def test_utils_dict_merge(self):
        r1 = {"relations": ["m1", "x1"]}
        r2 = {"relations": ["m2", "x2"]}
        combined = {"relations": ["m1", "m2", "x1", "x2"]}
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(
            sorted(combined["relations"]), sorted(test_result["relations"])
        )

    def test_utils_dict_merge_lists(self):
        r1 = ["m1", "x1"]
        r2 = ["m2", "x2"]
        combined = ["m1", "m2", "x1", "x2"]
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(sorted(combined), sorted(test_result))

    def test_utils_dict_merge_dicts(self):
        r1 = {"storage": {"/dev/sda": {"DEVTYPE": "disk"}}}
        r2 = {"storage": {"/dev/sda": {"ID_MODEL": "AWESOME"}}}
        combined = {
            "storage": {
                "/dev/sda": {
                    "DEVTYPE": "disk",
                    "ID_MODEL": "AWESOME",
                }
            }
        }
        test_result = utils.dict_merge(r1, r2)
        self.assertEqual(sorted(combined), sorted(test_result))

    def test_utils_read_sys_block_size_bytes(self):
        devname = random_string()
        expected_fname = "/sys/class/block/%s/size" % devname
        expected_bytes = 10737418240
        content = "20971520"
        with simple_mocked_open(content=content) as m_open:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            self.assertEqual([call(expected_fname)], m_open.call_args_list)

    def test_utils_read_sys_block_size_bytes_strips_value(self):
        devname = random_string()
        expected_fname = "/sys/class/block/%s/size" % devname
        expected_bytes = 10737418240
        content = " 20971520 \n "
        with simple_mocked_open(content=content) as m_open:
            result = utils.read_sys_block_size_bytes(devname)
            self.assertEqual(expected_bytes, result)
            self.assertEqual([call(expected_fname)], m_open.call_args_list)


@contextlib.contextmanager
def create_script(content):
    try:
        script = None
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            fp.write(textwrap.dedent(content))
            script = fp.name
        os.chmod(script, 0o755)
        yield script
    finally:
        if script:
            os.remove(script)


class ProbertTestRun(unittest.TestCase):
    leader = "DEBUG:probert.utils:"

    def test_run_success_no_output(self):
        content = """\
            #!/bin/sh
            exit 0
        """
        with self.assertLogs("probert.utils", level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, "a", "b", "c"])
            expected = [
                self.leader + line
                for line in (
                    f"Command `{script} a b c` exited with result: 0",
                    "<empty stdout>",
                    "<empty stderr>",
                    "--------------------------------------------------",
                )
            ]
            self.assertEqual("", actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_success_no_stderr(self):
        content = """\
            #!/bin/sh
            echo "Line 1"
            echo "Line 2"
            exit 0
        """
        with self.assertLogs("probert.utils", level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, "a", "b", "c"])
            expected = [
                self.leader + line
                for line in (
                    f"Command `{script} a b c` exited with result: 0",
                    "stdout: ------------------------------------------",
                    "Line 1",
                    "Line 2",
                    "<empty stderr>",
                    "--------------------------------------------------",
                )
            ]
            self.assertEqual("Line 1\nLine 2\n", actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_empty_output(self):
        content = """\
            #!/bin/sh
            echo
            exit 0
        """
        with self.assertLogs("probert.utils", level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, "a", "b", "c"])
            expected = [
                self.leader + line
                for line in (
                    f"Command `{script} a b c` exited with result: 0",
                    "stdout: ------------------------------------------",
                    "",
                    "<empty stderr>",
                    "--------------------------------------------------",
                )
            ]
            self.assertEqual("\n", actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_success_with_stderr(self):
        content = """\
            #!/bin/sh
            echo "Success message"
            echo "Diagnostic info" 1>&2
            exit 0
        """
        with self.assertLogs("probert.utils", level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script, "a", "b", "c"])
            expected = [
                self.leader + line
                for line in (
                    f"Command `{script} a b c` exited with result: 0",
                    "stdout: ------------------------------------------",
                    "Success message",
                    "stderr: ------------------------------------------",
                    "Diagnostic info",
                    "--------------------------------------------------",
                )
            ]
            self.assertEqual("Success message\n", actual)
            self.assertEqual(expected, m_logs.output)

    def test_run_failure(self):
        content = """\
            #!/bin/bash
            echo "Bad output"
            echo "You did it wrong" 1>&2
            exit 7
        """
        with self.assertLogs("probert.utils", level=logging.DEBUG) as m_logs:
            with create_script(content) as script:
                actual = utils.run([script])
            expected = [
                self.leader + line
                for line in (
                    f"Command `{script}` exited with result: 7",
                    "stdout: ------------------------------------------",
                    "Bad output",
                    "stderr: ------------------------------------------",
                    "You did it wrong",
                    "--------------------------------------------------",
                )
            ]
            self.assertIsNone(actual)
            self.assertEqual(expected, m_logs.output)


class ProbertTestArun(unittest.IsolatedAsyncioTestCase):
    def record_subprocesses(self):
        """Patch create_subprocess_exec so tests can inspect the child."""
        procs = []
        real_exec = asyncio.create_subprocess_exec

        async def exec_and_record(*args, **kwargs):
            proc = await real_exec(*args, **kwargs)
            procs.append(proc)
            return proc

        return procs, patch("asyncio.create_subprocess_exec", exec_and_record)

    async def test_arun_success_with_timeout(self):
        actual = await utils.arun(["echo", "hello"], timeout=10)
        self.assertEqual("hello\n", actual)

    async def test_arun_timeout_kills_command(self):
        procs, patcher = self.record_subprocesses()
        with patcher, self.assertLogs("probert.utils", level="DEBUG") as m_logs:
            actual = await asyncio.wait_for(
                utils.arun(["sleep", "30"], timeout=0.2), 20
            )
        self.assertIsNone(actual)
        self.assertEqual(-signal.SIGKILL, procs[0].returncode)
        self.assertIn("timed out after 0.2s, killed", "\n".join(m_logs.output))

    async def test_arun_cancelled_kills_command(self):
        procs, patcher = self.record_subprocesses()
        with patcher:
            task = asyncio.create_task(utils.arun(["sleep", "30"]))
            while not procs:
                await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 20)
        self.assertEqual(-signal.SIGKILL, procs[0].returncode)
