import subprocess
import unittest
from unittest import mock

from parameterized import parameterized

from probert import raid


class TestMdadmAssemble(unittest.TestCase):

    @parameterized.expand(
        [
            (
                subprocess.CalledProcessError(
                    cmd=["mdadm", "--detail", "--scan", "-v"], returncode=1
                ),
                "Failed mdadm_assemble command %s: %s",
                (["mdadm", "--detail", "--scan", "-v"], mock.ANY),
            ),
            (
                FileNotFoundError(),
                "Failed mdadm_assemble, mdadm command not found: %s",
                (mock.ANY,),
            ),
        ]
    )
    def test_mdadm_assemble__failure(self, exc, exp_msg, exp_args):
        with mock.patch("probert.raid.subprocess.run") as m_run:
            m_run.side_effect = exc
            with self.assertLogs("probert.raid", level="ERROR") as logs:
                raid.mdadm_assemble()
        self.assertEqual(logs.records[0].msg, exp_msg)
        self.assertEqual(logs.records[0].args, exp_args)
        m_run.assert_called_once_with(
            ["mdadm", "--detail", "--scan", "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )


class TestGetMdadmArrayMembers(unittest.TestCase):

    @mock.patch("probert.raid.subprocess.run")
    def test_get_mdadm_array_members_ok(self, m_run):
        output = "\n".join(
            [
                "MD_LEVEL=raid5",
                "MD_DEVICES=3",
                "MD_DEVICE_ev_dm_3_ROLE=1",
                "MD_DEVICE_ev_dm_3_DEV=/dev/dm-3",
                "MD_DEVICE_ev_dm_2_ROLE=0",
                "MD_DEVICE_ev_dm_2_DEV=/dev/dm-2",
                "MD_DEVICE_ev_dm_5_ROLE=spare",
                "MD_DEVICE_ev_dm_5_DEV=/dev/dm-5",
            ]
        )
        cp = subprocess.CompletedProcess(
            args=["mdadm"], returncode=0, stdout=output.encode("utf-8"), stderr=""
        )
        m_run.return_value = cp
        actives, spares = raid.get_mdadm_array_members("/dev/md0")
        self.assertEqual(["/dev/dm-2", "/dev/dm-3"], actives)
        self.assertEqual(["/dev/dm-5"], spares)
        m_run.assert_called_once_with(
            ["mdadm", "--detail", "--export", "/dev/md0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    def test_get_mdadm_array_members__calledprocesserror(self):
        exc = subprocess.CalledProcessError(
            cmd=["mdadm", "--detail", "--export", "/dev/md0"], returncode=1
        )
        with mock.patch("probert.raid.subprocess.run") as m_run:
            m_run.side_effect = exc
            with self.assertLogs("probert.raid", level="ERROR") as logs:
                result = raid.get_mdadm_array_members("/dev/md0")
        self.assertEqual(([], []), result)
        self.assertEqual(logs.records[0].msg, "failed to get detail for %s: %s")
        self.assertEqual(logs.records[0].args, ("/dev/md0", exc))
        m_run.assert_called_once_with(
            ["mdadm", "--detail", "--export", "/dev/md0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
