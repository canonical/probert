# Copyright 2021 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import random
import string
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from probert.filesystem import (get_btrfs_min_dev_size, get_btrfs_sizing,
                                get_device_filesystem, get_dumpe2fs_info,
                                get_ext_sizing, get_ntfs_sizing,
                                get_resize2fs_info, get_swap_sizing)


def read_file(filename):
    with open(filename, 'r') as fp:
        return fp.read()


def random_string(length=8):
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))


class TestGetSwapSizing(IsolatedAsyncioTestCase):
    async def test_expected_output_simple(self):
        device = {"ID_PART_ENTRY_SIZE": 2}
        expected = {"SIZE": 1024, "ESTIMATED_MIN_SIZE": 0}

        assert expected == await get_swap_sizing(device)

    async def test_expected_output_vg(self):
        device = {
            "DEVNAME": "/dev/dm-1",
            "DEVTYPE": "disk",
            "DM_VG_NAME": "vg1",
            "attrs": {
                "size": "1073741824",
            },
        }
        expected = {"SIZE": 1073741824, "ESTIMATED_MIN_SIZE": 0}

        assert expected == await get_swap_sizing(device)


class TestFilesystem(IsolatedAsyncioTestCase):
    def setUp(self):
        self.device = Mock()
        self.device.device_node = random_string()

    @patch('probert.filesystem.arun')
    async def test_dumpe2fs_simple_output(self, run):
        run.return_value = '''
Block count: 1234
Block size:  4000
'''
        expected = {'block_count': 1234, 'block_size': 4000}
        self.assertEqual(expected, await get_dumpe2fs_info(self.device))

    @patch('probert.filesystem.arun')
    async def test_dumpe2fs_real_output(self, run):
        run.return_value = read_file('probert/tests/data/dumpe2fs_ext4.out')
        expected = {'block_count': 10240, 'block_size': 4096}
        self.assertEqual(expected, await get_dumpe2fs_info(self.device))

    @patch('probert.filesystem.arun')
    async def test_resize2fs(self, run):
        run.return_value = 'Estimated minimum size of the filesystem: 1371\n'
        expected = {'min_blocks': 1371}
        self.assertEqual(expected, await get_resize2fs_info(self.device))

    @patch('probert.filesystem.get_resize2fs_info')
    @patch('probert.filesystem.get_dumpe2fs_info')
    async def test_ext4(self, dumpe2fs, resize2fs):
        dumpe2fs.return_value = {'block_count': 20000, 'block_size': 1000}
        resize2fs.return_value = {'min_blocks': 4000}
        expected = {'SIZE': 20000 * 1000, 'ESTIMATED_MIN_SIZE': 4000 * 1000}
        self.assertEqual(expected, await get_ext_sizing(self.device))

    @patch('probert.filesystem.get_dumpe2fs_info')
    async def test_ext4_bad_dumpe2fs(self, dumpe2fs):
        dumpe2fs.return_value = None
        self.assertIsNone(await get_ext_sizing(self.device))

    @patch('probert.filesystem.get_resize2fs_info')
    @patch('probert.filesystem.get_dumpe2fs_info')
    async def test_ext4_bad_resize2fs(self, dumpe2fs, resize2fs):
        dumpe2fs.return_value = {'block_count': 20000, 'block_size': 1000}
        resize2fs.return_value = None
        expected = {'SIZE': 20000 * 1000}
        self.assertEqual(expected, await get_ext_sizing(self.device))

    @patch('probert.filesystem.arun')
    @patch('probert.filesystem.shutil.which', Mock())
    async def test_ntfs_real_output(self, run):
        run.return_value = read_file('probert/tests/data/ntfsresize.out')
        expected = {'SIZE': 41939456, 'ESTIMATED_MIN_SIZE': 2613248}
        self.assertEqual(expected, await get_ntfs_sizing(self.device))

    @patch('probert.filesystem.arun')
    @patch('probert.filesystem.shutil.which', Mock())
    async def test_ntfs_real_output_full(self, run):
        run.return_value = read_file('probert/tests/data/ntfsresize_full.out')
        expected = {'SIZE': 83882496, 'ESTIMATED_MIN_SIZE': 83882496}
        self.assertEqual(expected, await get_ntfs_sizing(self.device))

    @patch('probert.filesystem.arun')
    @patch('probert.filesystem.shutil.which', Mock())
    async def test_ntfs_simple_output(self, run):
        run.return_value = '''
Current volume size: 100000000 bytes (100 MB)
You might resize at 25000000 bytes or 25 MB (freeing 75 MB).
'''
        expected = {'SIZE': 100000000, 'ESTIMATED_MIN_SIZE': 25000000}
        self.assertEqual(expected, await get_ntfs_sizing(self.device))

    async def test_swap_sizing(self):
        device = {'ID_PART_ENTRY_SIZE': 2}
        expected = {'SIZE': 1024, 'ESTIMATED_MIN_SIZE': 0}
        self.assertEqual(expected, await get_swap_sizing(device))

    async def test_swap_sizing_as_string(self):
        device = {'ID_PART_ENTRY_SIZE': "2"}
        expected = {'SIZE': 1024, 'ESTIMATED_MIN_SIZE': 0}
        self.assertEqual(expected, await get_swap_sizing(device))

    async def test_get_device_filesystem_no_sizing(self):
        data = {'ID_FS_FOO': 'bar'}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        expected = {'FOO': 'bar'}
        self.assertEqual(expected,
                         await get_device_filesystem(self.device, False))

    async def test_get_device_filesystem_sizing_unsupported(self):
        data = {'ID_FS_TYPE': 'reiserfs'}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        expected = {'ESTIMATED_MIN_SIZE': -1, 'TYPE': 'reiserfs'}
        self.assertEqual(expected,
                         await get_device_filesystem(self.device, True))

    async def test_get_device_filesystem_missing_info(self):
        data = {}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        expected = {'ESTIMATED_MIN_SIZE': -1}
        self.assertEqual(expected,
                         await get_device_filesystem(self.device, True))

    async def test_get_device_filesystem_sizing_ext4(self):
        data = {'ID_FS_TYPE': 'ext4'}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        size_info = {'ESTIMATED_MIN_SIZE': 1 << 20, 'SIZE': 10 << 20}
        ext4 = AsyncMock()
        ext4.return_value = size_info
        with patch.dict('probert.filesystem.sizing_tools',
                        {'ext4': ext4}, clear=True):
            expected = size_info.copy()
            expected['TYPE'] = 'ext4'
            actual = await get_device_filesystem(self.device, True)
            self.assertEqual(expected, actual)

    async def test_get_device_filesystem_sizing_ext4_no_min(self):
        data = {'ID_FS_TYPE': 'ext4'}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        size_info = {'SIZE': 10 << 20}
        ext4 = AsyncMock()
        ext4.return_value = size_info
        with patch.dict('probert.filesystem.sizing_tools',
                        {'ext4': ext4}, clear=True):
            expected = size_info.copy()
            expected['ESTIMATED_MIN_SIZE'] = -1
            expected['TYPE'] = 'ext4'
            actual = await get_device_filesystem(self.device, True)
            self.assertEqual(expected, actual)

    @patch('probert.filesystem.shutil.which')
    async def test_ntfsresize_not_found(self, which):
        which.return_value = None
        self.assertEqual(None, await get_ntfs_sizing(self.device))

    @patch('probert.filesystem.shutil.which')
    async def test_dumpe2fs_not_found(self, which):
        which.return_value = None
        self.assertEqual(None, await get_dumpe2fs_info(self.device))

    @patch('probert.filesystem.shutil.which')
    async def test_resize2fs_not_found(self, which):
        which.return_value = None
        self.assertEqual(None, await get_resize2fs_info(self.device))

    # Unlike other sizing tools, btrfs min-dev-size real output is just one
    # line, so a separate "real output" fixture test would be redundant.
    @patch('probert.filesystem.arun')
    @patch('probert.filesystem.shutil.which', Mock(return_value='/sbin/btrfs'))
    async def test_btrfs_min_dev_size(self, run):
        run.return_value = '104517861376 bytes (97.34GiB)\n'
        self.assertEqual(104517861376,
                         await get_btrfs_min_dev_size('/mnt/btrfs'))
        run.assert_awaited_once_with(
            ['/sbin/btrfs', 'inspect-internal', 'min-dev-size', '--',
             '/mnt/btrfs'])

    @patch('probert.filesystem.shutil.which')
    async def test_btrfs_min_dev_size_not_found(self, which):
        which.return_value = None
        self.assertIsNone(await get_btrfs_min_dev_size('/mnt/btrfs'))

    @patch('probert.filesystem.tempfile.TemporaryDirectory')
    @patch('probert.filesystem.arun', new_callable=AsyncMock)
    @patch('probert.filesystem.get_btrfs_min_dev_size', new_callable=AsyncMock)
    @patch('probert.filesystem._device_size_bytes')
    @patch('probert.filesystem.shutil.which', Mock(return_value='/sbin/btrfs'))
    async def test_btrfs_sizing(
            self, size_bytes, min_dev_size, run, tmpdir_cls):
        size_bytes.return_value = 2 << 30
        tmpdir_cls.return_value.__enter__.return_value = (
            '/tmp/probert-btrfs-test')
        run.return_value = 'num_devices\t\t1\n'
        min_dev_size.return_value = 500 << 20

        expected = {
            'SIZE': 2 << 30,
            'ESTIMATED_MIN_SIZE': 500 << 20,
        }
        self.assertEqual(expected, await get_btrfs_sizing(self.device))
        run.assert_any_await(
            ['mount', '-t', 'btrfs', '-o', 'ro', '--',
             self.device.device_node, '/tmp/probert-btrfs-test'])
        min_dev_size.assert_awaited_once_with('/tmp/probert-btrfs-test')
        run.assert_any_await(['umount', '--', '/tmp/probert-btrfs-test'])
        tmpdir_cls.return_value.__exit__.assert_called_once()

    @patch('probert.filesystem.arun', new_callable=AsyncMock)
    @patch('probert.filesystem._device_size_bytes')
    @patch('probert.filesystem.shutil.which', Mock(return_value='/sbin/btrfs'))
    async def test_btrfs_sizing_multi_device(self, size_bytes, run):
        size_bytes.return_value = 2 << 30
        run.return_value = 'num_devices\t\t2\n'

        expected = {'SIZE': 2 << 30, 'ESTIMATED_MIN_SIZE': -1}
        self.assertEqual(expected, await get_btrfs_sizing(self.device))
        run.assert_awaited_once_with(
            ['/sbin/btrfs', 'inspect-internal', 'dump-super', '--',
             self.device.device_node])

    @patch('probert.filesystem.shutil.which')
    async def test_btrfs_sizing_btrfs_not_found(self, which):
        which.return_value = None
        self.assertIsNone(await get_btrfs_sizing(self.device))

    @patch('probert.filesystem._device_size_bytes')
    @patch('probert.filesystem.shutil.which', Mock(return_value='/sbin/btrfs'))
    async def test_btrfs_sizing_no_device_size(self, size_bytes):
        size_bytes.return_value = 0
        self.assertIsNone(await get_btrfs_sizing(self.device))

    async def test_get_device_filesystem_sizing_btrfs(self):
        data = {'ID_FS_TYPE': 'btrfs'}
        self.device.properties = Mock()
        self.device.properties.__iter__ = Mock(return_value=iter(data))
        self.device.properties.__getitem__ = lambda _, x: data[x]
        size_info = {'ESTIMATED_MIN_SIZE': 1 << 20, 'SIZE': 10 << 20}
        btrfs = AsyncMock()
        btrfs.return_value = size_info
        with patch.dict('probert.filesystem.sizing_tools',
                        {'btrfs': btrfs}, clear=True):
            expected = size_info.copy()
            expected['TYPE'] = 'btrfs'
            actual = await get_device_filesystem(self.device, True)
            self.assertEqual(expected, actual)
