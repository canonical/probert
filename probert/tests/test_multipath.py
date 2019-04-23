import mock
import subprocess
import testtools

from probert import multipath
from probert.tests.helpers import random_string


class TestMultipath(testtools.TestCase):

    @mock.patch('probert.multipath.subprocess.run')
    def test_multipath_show_paths(self, m_run):
        mp_out = " ".join([random_string() for x in range(0, 8)])
        cp = subprocess.CompletedProcess(args=['foo'], returncode=0,
                                         stdout=mp_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = [multipath.MPath(*mp_out.split())._asdict()]
        result = multipath.multipath_show_paths()
        self.assertEqual(expected_result, result)

    @mock.patch('probert.multipath.subprocess.run')
    def test_multipath_show_paths_skips_unparsable_output(self, m_run):
        lines = ["1 2 3 4 5 6 7 8", "", "a b c d e f g h"]
        mp_out = "\n".join(lines)
        cp = subprocess.CompletedProcess(args=['foo'], returncode=0,
                                         stdout=mp_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = [multipath.MPath(*lines[0].split())._asdict(),
                           multipath.MPath(*lines[2].split())._asdict()]
        result = multipath.multipath_show_paths()
        self.assertEqual(expected_result, result)

    @mock.patch('probert.multipath.subprocess.run')
    def test_multipath_show_maps(self, m_run):
        mp_out = " ".join([random_string() for x in range(0, 3)])
        cp = subprocess.CompletedProcess(args=['foo'], returncode=0,
                                         stdout=mp_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = [multipath.MMap(*mp_out.split())._asdict()]
        result = multipath.multipath_show_maps()
        self.assertEqual(expected_result, result)

    @mock.patch('probert.multipath.subprocess.run')
    def test_multipath_show_maps_skips_unparsable_output(self, m_run):
        lines = ["1 2 3", "", "a b c"]
        mp_out = "\n".join(lines)
        cp = subprocess.CompletedProcess(args=['foo'], returncode=0,
                                         stdout=mp_out.encode('utf-8'),
                                         stderr="")
        m_run.return_value = cp
        expected_result = [multipath.MMap(*lines[0].split())._asdict(),
                           multipath.MMap(*lines[2].split())._asdict()]
        result = multipath.multipath_show_maps()
        self.assertEqual(expected_result, result)

    @mock.patch('probert.multipath.subprocess.run')
    def test_multipath_extract_returns_empty_list_on_err(self, m_run):
        m_run.side_effect = subprocess.CalledProcessError(cmd=["my cmd"],
                                                          returncode=1)
        result = multipath.multipath_show_paths()
        self.assertEqual([], result)

    @mock.patch('probert.multipath.multipath_show_paths')
    @mock.patch('probert.multipath.multipath_show_maps')
    def test_multipath_probe_collects_maps_and_paths(self, m_maps, m_paths):
        path_string = " ".join([random_string() for x in range(0, 8)])
        paths = multipath.MPath(*path_string.split())._asdict()
        maps_string = " ".join([random_string() for x in range(0, 3)])
        maps = multipath.MMap(*maps_string.split())._asdict()
        m_maps.return_value = [maps]
        m_paths.return_value = [paths]
        result = multipath.probe()
        self.assertDictEqual({'maps': [maps], 'paths': [paths]}, result)
