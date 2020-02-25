import mock
import subprocess
import testtools

from probert import dasd
from probert.tests import fakes
from probert.tests.helpers import random_string


class TestDasd(testtools.TestCase):

    def _load_test_data(self, data_fname):
        testfile = fakes.TEST_DATA + '/' + data_fname
        with open(testfile, 'r') as fh:
            return fh.read()

    @mock.patch('probert.dasd.os.path.exists')
    @mock.patch('probert.dasd.subprocess.run')
    def test_dasdview_returns_stdout(self, m_run, m_exists):
        devname = random_string()
        dasdview_out = random_string()
        cp = subprocess.CompletedProcess(args=['foo'], returncode=0,
                                         stdout=dasdview_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        m_exists.return_value = True
        result = dasd.dasdview(devname)
        self.assertEqual(dasdview_out, result)
        m_run.assert_called_with(['dasdview', '--extended', devname],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)

    @mock.patch('probert.dasd.os.path.exists')
    @mock.patch('probert.dasd.subprocess.run')
    def test_dasdview_raises_valueerror(self, m_run, m_exists):
        devname = random_string()
        m_exists.return_value = False
        self.assertRaises(ValueError, dasd.dasdview, devname)
        self.assertEqual(0, m_run.call_count)

    @mock.patch('probert.dasd.os.path.exists')
    @mock.patch('probert.dasd.subprocess.run')
    def test_dasdview_returns_none_on_subprocess_error(self, m_run, m_exists):
        devname = random_string()
        m_exists.return_value = True
        m_run.side_effect = subprocess.CalledProcessError(
            cmd=[random_string()], returncode=1)
        self.assertEqual(None, dasd.dasdview(devname))

    def test_dasd_parses_blocksize(self):
        self.assertEqual(4096,
                         dasd.blocksize(self._load_test_data('dasdd.view')))

    def test_dasd_blocksize_returns_none_on_invalid_output(self):
        self.assertIsNone(dasd.blocksize(random_string()))

    def test_dasd_parses_disk_format(self):
        self.assertEqual('cdl',
                         dasd.disk_format(self._load_test_data('dasdd.view')))
        self.assertEqual('not-formatted',
                         dasd.disk_format(self._load_test_data('dasde.view')))

    def test_dasd_parses_disk_format_ldl(self):
        output = "format : hex 1 dec 1 LDL formatted"
        self.assertEqual('ldl', dasd.disk_format(output))

    def test_dasd_disk_format_returns_none_on_invalid_output(self):
        self.assertIsNone(dasd.disk_format(random_string()))

    @mock.patch('probert.dasd.dasdview')
    def test_get_dasd_info(self, m_dview):
        devname = random_string()
        id_path = random_string()
        device = {'DEVNAME': devname, 'ID_PATH': 'ccw-' + id_path}
        m_dview.return_value = self._load_test_data('dasdd.view')
        self.assertEqual({'name': devname, 'device_id': id_path,
                          'disk_layout': 'cdl', 'blocksize': 4096},
                         dasd.get_dasd_info(device))

    @mock.patch('probert.dasd.dasdview')
    def test_get_dasd_info_returns_none_if_not_all(self, m_dview):
        devname = random_string()
        id_path = random_string()
        device = {'DEVNAME': devname, 'ID_PATH': 'ccw-' + id_path}
        m_dview.return_value = random_string()
        self.assertIsNone(dasd.get_dasd_info(device))

    @mock.patch('probert.dasd.blocksize')
    @mock.patch('probert.dasd.dasdview')
    def test_get_dasd_info_returns_none_if_bad_blocksize(self, m_dview,
                                                         m_block):
        devname = random_string()
        id_path = random_string()
        device = {'DEVNAME': devname, 'ID_PATH': 'ccw-' + id_path}
        m_dview.return_value = self._load_test_data('dasdd.view')
        m_block.return_value = None
        self.assertIsNone(dasd.get_dasd_info(device))

    @mock.patch('probert.dasd.blocksize')
    @mock.patch('probert.dasd.dasdview')
    def test_get_dasd_info_returns_none_if_bad_disk_format(self, m_dview,
                                                           m_disk):
        devname = random_string()
        id_path = random_string()
        device = {'DEVNAME': devname, 'ID_PATH': 'ccw-' + id_path}
        m_dview.return_value = self._load_test_data('dasdd.view')
        m_disk.return_value = None
        self.assertIsNone(dasd.get_dasd_info(device))

    @mock.patch('probert.dasd.platform.machine')
    def test_dasd_probe_returns_empty_dict_non_s390x_arch(self, m_machine):
        machine = random_string()
        self.assertNotEqual("s390x", machine)
        m_machine.return_value = machine
        self.assertEqual({}, dasd.probe())

    @mock.patch('probert.dasd.platform.machine')
    @mock.patch('probert.dasd.dasdview')
    def test_dasd_probe_dasdd(self, m_dasdview, m_machine):
        m_machine.return_value = 's390x'
        m_dasdview.side_effect = iter([self._load_test_data('dasdd.view')])

        context = mock.MagicMock()
        context.list_devices.side_effect = iter([
            [{"MAJOR": "94", "DEVNAME": "/dev/dasdd", "ID_SERIAL": "0X1544",
             "ID_PATH": "ccw-0.0.1544"}],
        ])
        expected_results = {
            '/dev/dasdd': {
                'name': '/dev/dasdd', 'device_id': '0.0.1544',
                'disk_layout': 'cdl', 'blocksize': 4096},
        }
        self.assertEqual(expected_results, dasd.probe(context=context))

    @mock.patch('probert.dasd.platform.machine')
    @mock.patch('probert.dasd.dasdview')
    def test_dasd_probe_dasde(self, m_dasdview, m_machine):
        m_machine.return_value = 's390x'
        m_dasdview.side_effect = iter([self._load_test_data('dasde.view')])

        context = mock.MagicMock()
        context.list_devices.side_effect = iter([
            [{"MAJOR": "94", "DEVNAME": "/dev/dasde",
             "ID_PATH": "ccw-0.0.2250"}],
        ])
        expected_results = {
            '/dev/dasde': {
                'name': '/dev/dasde', 'device_id': '0.0.2250',
                'disk_layout': 'not-formatted', 'blocksize': 512},
        }
        self.assertEqual(expected_results, dasd.probe(context=context))

    @mock.patch('probert.dasd.platform.machine')
    @mock.patch('probert.dasd.dasdview')
    def test_dasd_probe_dasdd_skips_partitions(self, m_dasdview, m_machine):
        m_machine.return_value = 's390x'
        m_dasdview.side_effect = iter([self._load_test_data('dasdd.view')])

        context = mock.MagicMock()
        context.list_devices.side_effect = iter([
            [{"MAJOR": "94", "DEVNAME": "/dev/dasdd", "ID_SERIAL": "0X1544",
             "ID_PATH": "ccw-0.0.1544"}],
            [{"MAJOR": "94", "DEVNAME": "/dev/dasdd1", "ID_SERIAL": "0X1544",
             "ID_PATH": "ccw-0.0.1544", "PARTN": "1"}],
        ])
        expected_results = {
            '/dev/dasdd': {
                'name': '/dev/dasdd', 'device_id': '0.0.1544',
                'disk_layout': 'cdl', 'blocksize': 4096},
        }
        self.assertEqual(expected_results, dasd.probe(context=context))
