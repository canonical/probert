# Copyright 2021 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
import string

from unittest import TestCase
from unittest.mock import Mock, patch

from probert.filesystem import (
    get_dumpe2fs_info,
    get_resize2fs_info,
    get_ext_sizing,
    get_ntfs_sizing,
    get_device_filesystem,
)


def read_file(filename):
    with open(filename, 'r') as fp:
        return fp.read()


def random_string(length=8):
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))


class TestFilesystem(TestCase):
    @patch('probert.filesystem.run')
    def test_dumpe2fs_simple_output(self, run):
        run.return_value = '''
Block count: 1234
Block size:  4000
'''
        expected = {'block_count': 1234, 'block_size': 4000}
        self.assertEqual(expected, get_dumpe2fs_info(random_string()))

    @patch('probert.filesystem.run')
    def test_dumpe2fs_real_output(self, run):
        run.return_value = read_file('probert/tests/data/dumpe2fs_ext4.out')
        expected = {'block_count': 10240, 'block_size': 4096}
        self.assertEqual(expected, get_dumpe2fs_info(random_string()))

    @patch('probert.filesystem.run')
    def test_resize2fs(self, run):
        run.return_value = 'Estimated minimum size of the filesystem: 1371\n'
        expected = {'min_blocks': 1371}
        self.assertEqual(expected, get_resize2fs_info(random_string()))

    @patch('probert.filesystem.get_resize2fs_info')
    @patch('probert.filesystem.get_dumpe2fs_info')
    def test_ext4(self, dumpe2fs, resize2fs):
        dumpe2fs.return_value = {'block_count': 20000, 'block_size': 1000}
        resize2fs.return_value = {'min_blocks': 4000}
        expected = {'SIZE': 20000 * 1000, 'ESTIMATED_MIN_SIZE': 4000 * 1000}
        self.assertEqual(expected, get_ext_sizing(random_string()))

    @patch('probert.filesystem.get_dumpe2fs_info')
    def test_ext4_bad_dumpe2fs(self, dumpe2fs):
        device = Mock()
        dumpe2fs.return_value = None
        self.assertIsNone(get_ext_sizing(device))

    @patch('probert.filesystem.get_resize2fs_info')
    @patch('probert.filesystem.get_dumpe2fs_info')
    def test_ext4_bad_resize2fs(self, dumpe2fs, resize2fs):
        device = Mock()
        dumpe2fs.return_value = {'block_count': 20000, 'block_size': 1000}
        resize2fs.return_value = None
        expected = {'SIZE': 20000 * 1000}
        self.assertEqual(expected, get_ext_sizing(device))

    @patch('probert.filesystem.run')
    def test_ntfs_real_output(self, run):
        run.return_value = read_file('probert/tests/data/ntfsresize.out')
        expected = {'SIZE': 41939456, 'ESTIMATED_MIN_SIZE': 2613248}
        self.assertEqual(expected, get_ntfs_sizing(random_string()))

    @patch('probert.filesystem.run')
    def test_ntfs_simple_output(self, run):
        run.return_value = '''
Current volume size: 100000000 bytes (100 MB)
You might resize at 25000000 bytes or 25 MB (freeing 75 MB).
'''
        expected = {'SIZE': 100000000, 'ESTIMATED_MIN_SIZE': 25000000}
        self.assertEqual(expected, get_ntfs_sizing(random_string()))

    def test_get_device_filesystem_no_sizing(self):
        data = {'ID_FS_FOO': 'bar'}
        device = Mock()
        device.items = lambda: data.items()
        expected = {'FOO': 'bar'}
        self.assertEqual(expected, get_device_filesystem(device, False))

    def test_get_device_filesystem_sizing_unsupported(self):
        data = {'ID_FS_TYPE': 'reiserfs'}
        device = Mock()
        device.items = lambda: data.items()
        expected = {'ESTIMATED_MIN_SIZE': -1, 'TYPE': 'reiserfs'}
        self.assertEqual(expected, get_device_filesystem(device, True))

    def test_get_device_filesystem_missing_info(self):
        data = {}
        device = Mock()
        device.items = lambda: data.items()
        expected = {'ESTIMATED_MIN_SIZE': -1}
        self.assertEqual(expected, get_device_filesystem(device, True))

    def test_get_device_filesystem_sizing_ext4(self):
        data = {'ID_FS_TYPE': 'ext4'}
        device = Mock()
        device.items = lambda: data.items()
        size_info = {'ESTIMATED_MIN_SIZE': 1 << 20, 'SIZE': 10 << 20}
        ext4 = Mock()
        ext4.return_value = size_info
        with patch.dict('probert.filesystem.sizing_tools',
                        {'ext4': ext4}, clear=True):
            expected = size_info.copy()
            expected['TYPE'] = 'ext4'
            actual = get_device_filesystem(device, True)
            self.assertEqual(expected, actual)

    def test_get_device_filesystem_sizing_ext4_no_min(self):
        data = {'ID_FS_TYPE': 'ext4'}
        device = Mock()
        device.items = lambda: data.items()
        size_info = {'SIZE': 10 << 20}
        ext4 = Mock()
        ext4.return_value = size_info
        with patch.dict('probert.filesystem.sizing_tools',
                        {'ext4': ext4}, clear=True):
            expected = size_info.copy()
            expected['ESTIMATED_MIN_SIZE'] = -1
            expected['TYPE'] = 'ext4'
            actual = get_device_filesystem(device, True)
            self.assertEqual(expected, actual)
