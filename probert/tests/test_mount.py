import json
import subprocess
import unittest
from unittest import mock

from parameterized import parameterized

from probert import mount


class TestFindmnt(unittest.TestCase):

    @mock.patch("probert.mount.subprocess.run")
    def test_findmnt_ok(self, m_run):
        filesystems = [{"target": "/", "fstype": "ext4"}]
        output = json.dumps({"filesystems": filesystems})
        cp = subprocess.CompletedProcess(
            args=["findmnt"], returncode=0, stdout=output.encode("utf-8"), stderr=""
        )
        m_run.return_value = cp
        result = mount.findmnt()
        self.assertEqual(filesystems, result.get("filesystems"))
        m_run.assert_called_once_with(
            ["findmnt", "--bytes", "--json", "-o", "+maj:min"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @parameterized.expand(
        [
            (subprocess.CalledProcessError(cmd=["findmnt"], returncode=1),),
            (FileNotFoundError(),),
        ]
    )
    def test_findmnt__failure(self, exc):
        with mock.patch("probert.mount.subprocess.run") as m_run:
            m_run.side_effect = exc
            result = mount.findmnt()
        self.assertEqual({}, result)
        m_run.assert_called_once_with(
            ["findmnt", "--bytes", "--json", "-o", "+maj:min"],
            stdout=mock.ANY,
            stderr=mock.ANY,
            check=True,
        )

    def test_findmnt_with_data(self):
        filesystems = [{"target": "/", "fstype": "ext4"}]
        data = json.dumps({"filesystems": filesystems})
        result = mount.findmnt(data=data)
        self.assertEqual(filesystems, result.get("filesystems"))

    def test_findmnt_with_data_bad_json(self):
        with self.assertLogs("probert.mount", level="ERROR") as logs:
            result = mount.findmnt(data="not json")
        self.assertEqual({}, result)
        self.assertEqual(logs.records[0].msg, "Failed to load findmnt json output: %s")
