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

import pyudev
from probert.utils import udev_get_attribute
import os


class Storage():
    def __init__(self):
        self.context = pyudev.Context()

    def get_device_size(self, device):
        ''' device='/dev/sda' '''
        with open(os.path.join('/sys/class/block',
                  os.path.basename(device), 'size')) as d:
            return d.read().strip()

    def probe(self):
        storage = {}
        for device in self.context.list_devices(subsystem='block'):
            if device['MAJOR'] not in ["1", "7"]:
                attrs = dict([(key, udev_get_attribute(device, key))
                              for key in device.attributes])
                if 'size' not in attrs:
                    attrs['size'] = \
                        str(self.get_device_size(device['DEVNAME']))
                storage[device['DEVNAME']] = dict(device)
                storage[device['DEVNAME']].update({'attrs': attrs})

        return storage
