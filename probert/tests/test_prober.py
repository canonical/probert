import unittest
from unittest.mock import patch

from probert.prober import Prober
from probert.firmware import FirmwareProber
from probert.storage import Storage
from probert.network import NetworkProber


class ProbertTestProber(unittest.IsolatedAsyncioTestCase):

    def test_prober_init(self):
        p = Prober()
        self.assertNotEqual(p, None)

    @patch.object(Prober, 'probe_all')
    async def test_prober_probe_all(self, _probe_all):
        p = Prober()
        await p.probe_all()
        self.assertTrue(_probe_all.called)

    @patch.object(Prober, 'probe_network')
    @patch.object(Prober, 'probe_storage')
    async def test_prober_probe_all_invoke_others(self, _storage, _network):
        p = Prober()
        await p.probe_all()
        self.assertTrue(_storage.called)
        self.assertTrue(_network.called)

    def test_prober_get_results(self):
        p = Prober()
        self.assertEqual({}, p.get_results())

    @patch.object(FirmwareProber, 'probe')
    @patch.object(NetworkProber, 'probe')
    @patch.object(Storage, 'probe')
    async def test_prober_probe_all_check_results(
            self, _storage, _network, _firmware):
        p = Prober()
        results = {
            'storage': {'lambic': 99},
            'network': {'saison': 99},
            'firmware': {'tripel': 99},
        }
        _storage.return_value = results['storage']
        _network.return_value = results['network']
        _firmware.return_value = results['firmware']
        await p.probe_all()
        self.assertTrue(_storage.called)
        self.assertTrue(_network.called)
        self.assertTrue(_firmware.called)
        self.assertEqual(results, p.get_results())
