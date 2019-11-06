import json
import mock
import subprocess
import testtools
import textwrap

from probert import lvm
from probert.tests.helpers import random_string

CONTEXT = [
  {
    "DEVNAME": "/dev/dm-0",
    "DEVTYPE": "disk",
    "DM_LV_NAME": "lv1",
    "DM_NAME": "vg1-lv1",
    "DM_UUID": "LVM-IBOfU1ELB4dehjpX2wy3BtkD504ARo0oclQZnCRnv2TGeopW5eZiP",
    "DM_VG_NAME": "vg1",
    "attrs": {
      "size": "1073741824",
    }
  }, {
    "DEVNAME": "/dev/vda5",
    "DEVTYPE": "partition",
    "ID_FS_TYPE": "LVM2_member",
    "USEC_INITIALIZED": "130182115",
    "attrs": {
      "size": "2147483648",
    }
  }, {
    "DEVNAME": "/dev/vda6",
    "DEVTYPE": "partition",
    "ID_FS_TYPE": "LVM2_member",
    "attrs": {
      "size": "3221225472",
    }
  },
]

VGS_REPORT = [
    {
        "vg_name": "vg1",
        "pv_name": "/dev/vda5",
        "pv_uuid": "46GvlZ-5UAL-tvnf-AX60-3pwg-A9p3-5pBAq6",
        "vg_size": "206145847296B"
    }, {
        "vg_name": "vg1",
        "pv_name": "/dev/vda6",
        "pv_uuid": "J3bQo5-scWX-fIwg-Je9J-LkRC-rkLp-1X6KPg",
        "vg_size": "206145847296B"
    },
]

CONTEXT_DUPES = 2 * CONTEXT + [
  {
    "DEVNAME": "/dev/dm-1",
    "DEVTYPE": "disk",
    "DM_LV_NAME": "lv2",
    "DM_NAME": "vg1-lv2",
    "DM_UUID": "LVM-IBOfU1ELB4dehjpX2wy3BtkD504ARo0oclQZnCRnv2TGeopW5eZiP",
    "DM_VG_NAME": "vg1",
    "attrs": {
      "size": "1073741824",
    }
  },
]
VGS_REPORT_DUPES = 2 * VGS_REPORT


@mock.patch('probert.lvm.subprocess.run')
class TestLvm(testtools.TestCase):

    def test__lvm_report_returns_empty_list_on_err(self, m_run):
        m_run.side_effect = subprocess.CalledProcessError(
            cmd=[random_string()], returncode=1)
        result = lvm._lvm_report(random_string(), random_string())
        self.assertEqual([], result)

    def test__lvm_report_returns_empty_list_on_no_output(self, m_run):
        cmd_out = ""
        cp = subprocess.CompletedProcess(args=[random_string()], returncode=0,
                                         stdout=cmd_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        self.assertEqual([], lvm._lvm_report(random_string(), random_string()))

    def test__lvm_report_returns_empty_list_on_invalid_json(self, m_run):
        cmd_out = "This is not json"
        cp = subprocess.CompletedProcess(args=[random_string()], returncode=0,
                                         stdout=cmd_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        self.assertEqual([], lvm._lvm_report(random_string(), random_string()))

    def test__lvm_report_returns_found_reports(self, m_run):
        report_key = random_string()
        report_data = [{random_string(): random_string()}]
        cmd_out = json.dumps({"report": [{report_key: report_data}]})
        cp = subprocess.CompletedProcess(args=[random_string()], returncode=0,
                                         stdout=cmd_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = report_data
        result = lvm._lvm_report(random_string(), report_key)
        self.assertEqual(expected_result, result)

    def test__lvm_report_returns_specific_reports(self, m_run):
        report_key = 'report-1'
        report_data = [{random_string(): random_string()}]
        extra_data1 = [list(range(0, 10))]
        extra_data2 = ""
        cmd_out = json.dumps({
            "report": [
                {report_key: report_data},
                {random_string(): extra_data1},
                {random_string(): extra_data2},
             ]
        })
        cp = subprocess.CompletedProcess(args=[random_string()], returncode=0,
                                         stdout=cmd_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = report_data
        result = lvm._lvm_report(random_string(), report_key)
        self.assertEqual(expected_result, result)

    @mock.patch('probert.lvm._lvm_report')
    def test_probe_pvs_report_calls_pvs(self, m_lvreport, m_run):
        lvm.probe_pvs_report()
        m_lvreport.assert_called_with(['pvs', '--reportformat=json'], 'pv')

    @mock.patch('probert.lvm._lvm_report')
    def test_probe_vgs_report_calls_vgs(self, m_lvreport, m_run):
        lvm.probe_vgs_report()
        m_lvreport.assert_called_with(
            ['vgs', '--reportformat=json', '--units=B',
             '-o', 'vg_name,pv_name,pv_uuid,vg_size'], 'vg')

    @mock.patch('probert.lvm._lvm_report')
    def test_probe_lvs_report_calls_lvs(self, m_lvreport, m_run):
        lvm.probe_lvs_report()
        m_lvreport.assert_called_with(['lvs'], 'lv')

    @mock.patch('probert.lvm.os.environ')
    def test_lvmetad_running(self, m_env, m_run):
        m_env.return_value = {'LVM_LVMETA_D_PIDFILE': '/run/lvmetad.pid'}
        self.assertTrue(lvm.lvmetad_running())

    @mock.patch('probert.lvm.os.environ.get')
    @mock.patch('probert.lvm.os.path.exists')
    def test_lvmetad_running_env_get(self, m_path, m_env, m_run):
        pidfile = random_string()
        m_env.return_value = pidfile
        m_path.return_value = True
        self.assertTrue(lvm.lvmetad_running())
        m_env.assert_called_with('LVM_LVMETAD_PIDFILE', '/run/lvmetad.pid')
        m_path.assert_called_with(pidfile)

    @mock.patch('probert.lvm.os.environ')
    @mock.patch('probert.lvm.os.path.exists')
    def test_lvmetad_running_env_empty(self, m_path, m_env, m_run):
        pidfile = '/run/lvmetad.pid'
        m_env.get.return_value = pidfile
        m_path.return_value = True
        self.assertTrue(lvm.lvmetad_running())
        m_path.assert_called_with(pidfile)

    @mock.patch('probert.lvm.os.environ')
    @mock.patch('probert.lvm.os.path.exists')
    def test_lvmetad_running_false_if_path_fails(self, m_path, m_env, m_run):
        m_path.return_value = False
        self.assertFalse(lvm.lvmetad_running())

    @mock.patch('probert.lvm.lvmetad_running')
    def test_lvm_scan(self, m_metad, m_run):
        m_metad.return_value = True
        lvm.lvm_scan()
        self.assertEqual(2, m_metad.call_count)
        m_run.assert_has_calls([
          mock.call(['pvscan', '--cache'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
          mock.call(['vgscan', '--mknodes', '--cache'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)])

    @mock.patch('probert.lvm.lvmetad_running')
    def test_lvm_scan_handles_errors(self, m_metad, m_run):
        m_metad.return_value = True
        m_run.side_effect = iter([
            subprocess.CalledProcessError(cmd="foo", returncode=1),
            subprocess.CalledProcessError(cmd="foo", returncode=1),
        ])
        lvm.lvm_scan()
        self.assertEqual(2, m_metad.call_count)
        m_run.assert_has_calls([
          mock.call(['pvscan', '--cache'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
          mock.call(['vgscan', '--mknodes', '--cache'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)])

    def test_activate_volgroups(self, m_run):
        lvm.activate_volgroups()
        m_run.assert_has_calls([
          mock.call(['vgchange', '--activate=y'], check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)])

    def test_extract_lvm_volgroup(self, m_run):
        input_data = json.loads(
            textwrap.dedent("""
                [
                    {"vg_name": "vg0",
                     "pv_name": "/dev/md0",
                     "pv_uuid": "p3oDow-dRHp-L8jq-t6gQ-67tv-B8B6-JWLKZP",
                     "vg_size": "1000B"},
                    {"vg_name": "vg0",
                     "pv_name": "/dev/md1",
                     "pv_uuid": "pRR5Zn-c4a9-teVZ-TFaU-yDxf-FSDo-cORcEq",
                     "vg_size": "21449670656B"},
                    {"vg_name": "vg0",
                     "pv_name": "/dev/md2",
                     "pv_uuid": "Xsjd5a-c4a9-teVZ-TFaU-yDxf-FSDo-cORcEq",
                     "vg_size": "doesnt_end_with_B_"}
                ]"""))
        self.assertEqual(
            ("vg0", {'name': "vg0",
                     'devices': sorted(['/dev/md0', '/dev/md1', '/dev/md2']),
                     'size': '21449670656B'}),
            lvm.extract_lvm_volgroup('vg0', input_data))

    def test_extract_lvm_volgroup_no_size_set_to_zero_bytes(self, m_run):
        input_data = json.loads(
            textwrap.dedent("""
                [
                    {"vg_name": "vg0",
                     "pv_name": "/dev/md0",
                     "pv_uuid": "p3oDow-dRHp-L8jq-t6gQ-67tv-B8B6-JWLKZP",
                     "vg_size": null},
                    {"vg_name": "vg0",
                     "pv_name": "/dev/md1",
                     "pv_uuid": "pRR5Zn-c4a9-teVZ-TFaU-yDxf-FSDo-cORcEq",
                     "vg_size": null}
                ]"""))
        self.assertEqual(
            ("vg0", {'name': "vg0",
                     'devices': sorted(['/dev/md0', '/dev/md1']),
                     'size': '0B'}),
            lvm.extract_lvm_volgroup('vg0', input_data))

    @mock.patch('probert.lvm.read_sys_block_size_bytes')
    def test_extract_lvm_partition(self, m_size, m_run):
        size = 100000000
        m_size.return_value = size
        input_data = {
            'DEVNAME': '/dev/dm-2',
            'DM_NAME': 'ubuntu--vg-my--storage',
            'DM_LV_NAME': 'my-storage',
            'DM_VG_NAME': 'ubuntu-vg',
        }
        self.assertEqual(
            ('ubuntu-vg/my-storage',
             {'fullname': 'ubuntu-vg/my-storage', 'name': 'my-storage',
              'volgroup': 'ubuntu-vg', 'size': "%sB" % size}),
            lvm.extract_lvm_partition(input_data))
        m_size.assert_called_with('/dev/dm-2')

    @mock.patch('probert.lvm.read_sys_block_size_bytes')
    @mock.patch('probert.lvm.activate_volgroups')
    @mock.patch('probert.lvm.lvm_scan')
    @mock.patch('probert.lvm.pyudev.Context.list_devices')
    @mock.patch('probert.lvm.probe_vgs_report')
    def test_probe(self, m_vgs, m_pyudev, m_scan, m_activate, m_size, m_run):
        size = 1000
        m_size.return_value = size
        m_pyudev.return_value = CONTEXT
        m_vgs.return_value = VGS_REPORT

        expected_result = {
            'logical_volumes': {
                'vg1/lv1': {
                    'fullname': 'vg1/lv1',
                    'name': 'lv1',
                    'size': '1000B',
                    'volgroup': 'vg1'
                }
            },
            'physical_volumes': {
                'vg1': ['/dev/vda5', '/dev/vda6']
            },
            'volume_groups': {
                'vg1': {
                    'devices': ['/dev/vda5', '/dev/vda6'],
                    'name': 'vg1',
                    'size': '206145847296B'
                }
            }
        }
        self.assertEqual(expected_result, lvm.probe())

    @mock.patch('probert.lvm.read_sys_block_size_bytes')
    @mock.patch('probert.lvm.activate_volgroups')
    @mock.patch('probert.lvm.lvm_scan')
    @mock.patch('probert.lvm.pyudev.Context.list_devices')
    @mock.patch('probert.lvm.probe_vgs_report')
    def test_probe_skip_dupes(self, m_vgs, m_pyudev, m_scan, m_activate,
                              m_size, m_run):
        size = 1000
        m_size.return_value = size
        m_pyudev.return_value = CONTEXT_DUPES
        m_vgs.return_value = VGS_REPORT_DUPES

        expected_result = {
            'logical_volumes': {
                'vg1/lv1': {
                    'fullname': 'vg1/lv1',
                    'name': 'lv1',
                    'size': '1000B',
                    'volgroup': 'vg1'
                },
                'vg1/lv2': {
                    'fullname': 'vg1/lv2',
                    'name': 'lv2',
                    'size': '1000B',
                    'volgroup': 'vg1'
                },
            },
            'physical_volumes': {
                'vg1': ['/dev/vda5', '/dev/vda6']
            },
            'volume_groups': {
                'vg1': {
                    'devices': ['/dev/vda5', '/dev/vda6'],
                    'name': 'vg1',
                    'size': '206145847296B'
                }
            }
        }
        self.assertEqual(expected_result, lvm.probe())


# vi: ts=4 expandtab syntax=python
