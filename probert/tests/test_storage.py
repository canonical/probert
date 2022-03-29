import testtools
from unittest.mock import Mock
import json

from probert.storage import Storage, StorageInfo
from probert.tests.fakes import FAKE_PROBE_ALL_JSON


class ProbertTestStorage(testtools.TestCase):
    def setUp(self):
        super(ProbertTestStorage, self).setUp()

    def test_storage_init(self):
        with open(FAKE_PROBE_ALL_JSON) as f:
            self.results = json.load(f)
        storage = Storage(results=self.results)
        self.assertNotEqual(None, storage)


class ProbertTestStorageProbeSet(testtools.TestCase):
    def setUp(self):
        super(ProbertTestStorageProbeSet, self).setUp()
        self.storage = Storage()
        for k, v in self.storage.probe_map.items():
            self.storage.probe_map[k].pfunc = Mock()

    def _do_test_defaults(self, probe_types):
        self.storage.probe(probe_types)
        for k, v in self.storage.probe_map.items():
            if (probe_types and k in probe_types) or v.in_default_set:
                v.pfunc.assert_called()
            else:
                v.pfunc.assert_not_called()

    def test_storage_none_probe_types(self):
        self._do_test_defaults(None)

    def test_storage_defaults_probe_types(self):
        self._do_test_defaults({'defaults'})

    def test_storage_defaults_with_extra_probe_types(self):
        self._do_test_defaults({'defaults', 'os'})

    def test_storage_some_probe_types(self):
        probe_types = {'bcache'}
        self.storage.probe(probe_types)
        for k, v in self.storage.probe_map.items():
            if k in probe_types:
                v.pfunc.assert_called()
            else:
                v.pfunc.assert_not_called()

    def test_storage_unknown_type(self):
        probe_types = {'not-a-real-type'}
        self.storage.probe(probe_types)
        for v in self.storage.probe_map.values():
            v.pfunc.assert_not_called()


class ProbertTestStorageInfo(testtools.TestCase):
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
