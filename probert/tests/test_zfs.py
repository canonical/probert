import subprocess
import unittest
from unittest import mock

from parameterized import parameterized

from probert import zfs


class TestZdbAsdict(unittest.TestCase):
    @mock.patch("probert.zfs.os.path.exists")
    @mock.patch("probert.zfs.subprocess.run")
    def test_zdb_asdict_with_data(self, m_run, m_exists):
        m_exists.return_value = True
        result = zfs.zdb_asdict(data="test_pool:\n    version: 5000\n")
        self.assertIn("test_pool", result)
        m_run.assert_not_called()

    @parameterized.expand(
        [
            (subprocess.CalledProcessError(cmd=["zdb"], returncode=1),),
            (FileNotFoundError(),),
        ]
    )
    def test_zdb_asdict__failure(self, exc):
        with (
            mock.patch("probert.zfs.os.path.exists", return_value=True),
            mock.patch("probert.zfs.subprocess.run") as m_run,
        ):
            m_run.side_effect = exc
            result = zfs.zdb_asdict()
        self.assertEqual({}, result)
        m_run.assert_called_once_with(
            ["zdb"], stdout=mock.ANY, stderr=mock.ANY, check=True
        )


class TestZfsListFilesystems(unittest.TestCase):
    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_list_filesystems_ok(self, m_run):
        output = "tank\t118272\t0\t118272\t/\n"
        cp = subprocess.CompletedProcess(
            args=["zfs"], returncode=0, stdout=output.encode("utf-8"), stderr=""
        )
        m_run.return_value = cp
        result = zfs.zfs_list_filesystems()
        self.assertEqual(1, len(result))
        self.assertEqual("tank", result[0].name)
        m_run.assert_called_once_with(
            ["zfs", "list", "-Hp", "-t", "filesystem"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_list_filesystems__calledprocesserror(self, m_run):
        m_run.side_effect = subprocess.CalledProcessError(cmd=["zfs"], returncode=1)
        result = zfs.zfs_list_filesystems()
        self.assertEqual([], result)
        m_run.assert_called_once_with(
            ["zfs", "list", "-Hp", "-t", "filesystem"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_list_filesystems_raw(self, m_run):
        output = "tank\t118272\t0\t118272\t/\n"
        cp = subprocess.CompletedProcess(
            args=["zfs"], returncode=0, stdout=output.encode("utf-8"), stderr=""
        )
        m_run.return_value = cp
        result = zfs.zfs_list_filesystems(raw_output=True)
        self.assertEqual(output, result)


class TestZfsGetProperties(unittest.TestCase):
    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_get_properties_ok(self, m_run):
        output = """\
tank\ttype\tfilesystem\t-'
tank\tused\t118272\t-
tank\tquota\t0\tdefault
"""
        m_run.return_value.stdout = output.encode("utf-8")
        result = zfs.zfs_get_properties("tank")
        self.assertIn("tank", result)
        self.assertEqual("118272", result["tank"]["properties"]["used"]["value"])
        self.assertEqual("0", result["tank"]["properties"]["quota"]["value"])
        self.assertEqual("default", result["tank"]["properties"]["quota"]["source"])

    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_get_properties__calledprocesserror(self, m_run):
        m_run.side_effect = subprocess.CalledProcessError(cmd=["zfs"], returncode=1)
        result = zfs.zfs_get_properties("tank")
        self.assertEqual([], result)
        m_run.assert_called_once_with(
            ["zfs", "get", "all", "-Hp", "tank"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @mock.patch("probert.zfs.subprocess.run")
    def test_zfs_get_properties_empty_name(self, m_run):
        with self.assertRaises(ValueError) as m_exc:
            zfs.zfs_get_properties("")
        self.assertEqual('Invalid zfs_name parameter: ""', str(m_exc.exception))
