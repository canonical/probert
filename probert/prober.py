# Copyright 2015 Canonical, Ltd.
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

from probert.lvm import LVM
from probert.network import NetworkProber
from probert.raid import MDADM
from probert.storage import Storage


class Prober():
    def __init__(self):
        self._results = {}
        self._config = {}

    def probe_all(self):
        self.probe_storage()
        self.probe_network()
        self.probe_lvm()
        self.probe_raid()

    def probe_storage(self):
        self._storage = Storage()
        self._results['storage'] = self._storage.probe()
        self._config['storage'] = self._storage.export()

    def probe_lvm(self):
        self._lvm = LVM()
        self._results['lvm'] = self._lvm.probe(report=True)
        self._config['lvm'] = self._lvm.export()

    def probe_network(self):
        self._network = NetworkProber()
        self._results['network'] = self._network.probe()
        self._config['network'] = self._network.export()

    def probe_raid(self):
        self._raid = MDADM()
        self._results['raid'] = self._raid.probe(report=True)
        self._config['raid'] = self._raid.export()

    def get_results(self):
        return self._results

    def export_config(self):
        return self._config
