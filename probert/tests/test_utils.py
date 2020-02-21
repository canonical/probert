import testtools
from mock import call, patch

from probert import utils
from probert.tests.helpers import random_string


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

    @patch('probert.utils.load_file')
    def test_utils_read_sys_block_size_bytes(self, m_load_file):
        devname = random_string()
        expected_fname = '/sys/class/block/%s/size' % devname
        expected_bytes = 10737418240
        content = '20971520'
        m_load_file.return_value = content.encode('utf-8')
        result = utils.read_sys_block_size_bytes(devname)
        self.assertEqual(expected_bytes, result)
        self.assertEqual([call(expected_fname)], m_load_file.call_args_list)

    @patch('probert.utils.load_file')
    def test_utils_read_sys_block_size_bytes_strips_value(self, m_load_file):
        devname = random_string()
        expected_fname = '/sys/class/block/%s/size' % devname
        expected_bytes = 10737418240
        content = ' 20971520 \n '
        m_load_file.return_value = content.encode('utf-8')
        result = utils.read_sys_block_size_bytes(devname)
        self.assertEqual(expected_bytes, result)
        self.assertEqual([call(expected_fname)], m_load_file.call_args_list)
