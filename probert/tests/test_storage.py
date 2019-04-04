import testtools
import json

from probert.storage import Storage, StorageInfo
from probert.tests.fakes import FAKE_PROBE_ALL_JSON


class ProbertTestStorage(testtools.TestCase):
    def setUp(self):
        super(ProbertTestStorage, self).setUp()
        with open(FAKE_PROBE_ALL_JSON) as f:
            self.results = json.load(f)
        self.storage = Storage(results=self.results)

    def test_storage_init(self):
        self.assertNotEqual(None, self.storage)


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
            'devpath': '/devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda',
            'is_virtual': False,
            'raw': sda.get('/dev/sda')
        }
        for (prop, value) in props.items():
            self.assertEqual(getattr(si, prop), value)
