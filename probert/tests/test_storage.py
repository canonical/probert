import json
import subprocess
import unittest
from unittest import mock
from unittest.mock import AsyncMock, Mock

from parameterized import parameterized

from probert.storage import (Storage, StorageInfo, blockdev_probe,
                             interesting_storage_devs)
from probert.tests.fakes import FAKE_PROBE_ALL_JSON


class ProbertTestInterestingDevs(unittest.TestCase):
    @parameterized.expand([
        ['1', 0],
        ['2', 1],
        ['7', 0],
    ])
    def test_major_filtering(self, major, expected):
        context = Mock()
        context.list_devices.return_value = [{'MAJOR': major}]

        actual = len(list(interesting_storage_devs(context)))
        self.assertEqual(expected, actual)

    @parameterized.expand([
        ['7:0', 0],
        ['8:0', 1],
    ])
    def test_parent_major_filtering(self, parent_majmin, expected):
        context = Mock()
        context.list_devices.return_value = [{
            'MAJOR': '259',
            'ID_PART_ENTRY_DISK': parent_majmin
        }]

        actual = len(list(interesting_storage_devs(context)))
        self.assertEqual(expected, actual)


class ProbertTestStorage(unittest.TestCase):
    def setUp(self):
        super(ProbertTestStorage, self).setUp()

    def test_storage_init(self):
        with open(FAKE_PROBE_ALL_JSON) as f:
            self.results = json.load(f)
        storage = Storage(results=self.results)
        self.assertNotEqual(None, storage)


class ProbertTestStorageProbeSet(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super(ProbertTestStorageProbeSet, self).setUp()
        self.storage = Storage()
        for k, v in self.storage.probe_map.items():
            self.storage.probe_map[k].pfunc = AsyncMock()

    async def _do_test_defaults(self, probe_types):
        await self.storage.probe(probe_types)
        for k, v in self.storage.probe_map.items():
            if (probe_types and k in probe_types) or v.in_default_set:
                v.pfunc.assert_called()
            else:
                v.pfunc.assert_not_called()

    async def test_storage_none_probe_types(self):
        await self._do_test_defaults(None)

    async def test_storage_defaults_probe_types(self):
        await self._do_test_defaults({'defaults'})

    async def test_storage_defaults_with_extra_probe_types(self):
        await self._do_test_defaults({'defaults', 'os'})

    async def test_storage_some_probe_types(self):
        probe_types = {'bcache'}
        await self.storage.probe(probe_types)
        for k, v in self.storage.probe_map.items():
            if k in probe_types:
                v.pfunc.assert_called()
            else:
                v.pfunc.assert_not_called()

    async def test_storage_unknown_type(self):
        probe_types = {'not-a-real-type'}
        await self.storage.probe(probe_types)
        for v in self.storage.probe_map.values():
            v.pfunc.assert_not_called()


class TestBlockdevProbe(unittest.IsolatedAsyncioTestCase):
    # Lots of mocks because _extract_partition_table is a nested function
    # inside blockdev_probe — testing sfdisk's failure path requires
    # patching everything that blockdev_probe touches.
    @mock.patch('probert.storage.subprocess.run')
    @mock.patch('probert.storage.read_sys_block_size_bytes')
    @mock.patch('probert.storage.udev_get_attributes')
    @mock.patch('probert.storage.interesting_storage_devs')
    @mock.patch('probert.storage.pyudev')
    async def test_extract_partition_table_sfdisk_failure(
            self, m_pyudev, m_interesting, m_udev_attr, m_read_sys, m_run):
        devname = '/dev/sda'
        m_interesting.return_value = [
            mock.MagicMock(
                properties={'DEVNAME': devname})]
        m_udev_attr.return_value = {'size': '1000'}
        m_read_sys.return_value = 1000
        err = subprocess.CalledProcessError(
            cmd=['sfdisk'], returncode=1)
        m_run.side_effect = err

        with self.assertLogs('probert.storage', level='ERROR') as logs:
            result = await blockdev_probe(context=mock.MagicMock())
        self.assertIn(devname, result)
        self.assertNotIn('pttype', result[devname])
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(
            logs.records[0].msg,
            'Failed to probe partition table on %s:%s')
        self.assertEqual(logs.records[0].args, (devname, err))
        m_run.assert_called_with(
            ['sfdisk', '--bytes', '--json', devname],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=True)


class ProbertTestStorageInfo(unittest.TestCase):
    ''' properties:
        .name = /dev/sda
        .type = disk
        .vendor = SanDisk
        .model = SanDisk_12123123
        .serial = aaccasdf
        .devpath = /devices
        .is_virtual =
        .raw = {raw dictionary}
    '''
    def setUp(self):
        super(ProbertTestStorageInfo, self).setUp()
        with open(FAKE_PROBE_ALL_JSON) as f:
            self.results = json.load(f)

    def test_storageinfo_init(self):
        probe_data = {
            '/dev/sda': {
                'DEVTYPE': 'disk',
                'attrs': {
                    'size': '1000000'
                }
            }
        }
        si = StorageInfo(probe_data)
        self.assertNotEqual(si, None)

    def test_storageinfo_attributes(self):
        sda = {'/dev/sda': self.results.get('storage').get('/dev/sda')}
        si = StorageInfo(probe_data=sda)
        props = {
            'name': '/dev/sda',
            'type': 'disk',
            'vendor': 'SanDisk',
            'model': 'SanDisk_SD5SG2128G1052E',
            'serial': 'SanDisk_SD5SG2128G1052E_133507400177',
            'devpath': (
                '/devices/pci0000:00/0000:00:1f.2/ata1/'
                'host0/target0:0:0/0:0:0:0/block/sda'
            ),
            'is_virtual': False,
            'raw': sda.get('/dev/sda')
        }
        for (prop, value) in props.items():
            self.assertEqual(getattr(si, prop), value)
