# Copyright 2015 Canonical, Ltd.
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


class Prober():
    def __init__(self):
        self._results = {}

    async def probe_all(self, *, parallelize=False):
        await self.probe_storage()
        self.probe_network()

    async def probe_storage(self, *, parallelize=False):
        from probert.storage import Storage
        self._storage = Storage()
        self._results['storage'] = await self._storage.probe(
                parallelize=parallelize)

    def probe_network(self):
        from probert.network import NetworkProber
        self._network = NetworkProber()
        self._results['network'] = self._network.probe()

    def get_results(self):
        return self._results
