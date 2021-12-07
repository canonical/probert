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

import json
import logging
import pyudev
import subprocess

from probert.utils import (
    read_sys_block_size_bytes,
    sane_block_devices,
    udev_get_attributes,
    )
from probert import (bcache, dasd, dmcrypt, filesystem, lvm, mount, multipath,
                     os, raid, zfs)

log = logging.getLogger('probert.storage')


class StorageInfo():
    ''' properties:
        .type = [disk, partition, etc.}
        .name = /dev/sda
        .size = 123012034 (bytes)
        .serial = abcdefghijkl
        .vendor = Innotec
        .model = SolidStateRocketDrive
        .devpath = /devices
        .is_virtual =
        .raw = {raw dictionary}
    '''
    def __init__(self, probe_data):
        [self.name] = probe_data
        self.raw = probe_data.get(self.name)

        self.type = self.raw['DEVTYPE']
        self.size = int(self.raw['attrs']['size'])

    def _get_hwvalues(self, keys):
        for key in keys:
            try:
                return self.raw[key]
            except KeyError:
                log.debug(
                    'Failed to get key {} from interface {}'.format(key,
                                                                    self.name))

        return None

    @property
    def vendor(self):
        ''' Some disks don't have ID_VENDOR_* instead the vendor
            is encoded in the model: SanDisk_A223JJ3J3 '''
        v = self._get_hwvalues(['ID_VENDOR_FROM_DATABASE', 'ID_VENDOR',
                                'ID_VENDOR_ID'])
        if v is None:
            v = self.model
            if v is not None:
                return v.split('_')[0]
        return v

    @property
    def model(self):
        return self._get_hwvalues(['ID_MODEL_FROM_DATABASE', 'ID_MODEL',
                                   'ID_MODEL_ID'])

    @property
    def serial(self):
        return self._get_hwvalues(['ID_SERIAL', 'ID_SERIAL_SHORT'])

    @property
    def devpath(self):
        return self._get_hwvalues(['DEVPATH'])

    @property
    def is_virtual(self):
        return self.devpath.startswith('/devices/virtual/')


def blockdev_probe(context=None):
    """ Non-class method for extracting relevant block
        devices from pyudev.Context().
    """
    def _extract_partition_table(devname):
        cmd = ['sfdisk', '--bytes', '--json', devname]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
            output = result.stdout.decode('utf-8')
        except subprocess.CalledProcessError as e:
            log.error('Failed to probe partition table on %s:%s', devname, e)
            return None
        if not output:
            return None
        ptable = {}
        try:
            ptable = json.loads(output)
        except json.decoder.JSONDecodeError:
            log.exception('Failed to load sfdisk json output:')
        return ptable

    if not context:
        context = pyudev.Context()

    blockdev = {}
    for device in sane_block_devices(context):
        if device['MAJOR'] not in ["1", "7"]:
            attrs = udev_get_attributes(device)
            # update the size attr as it may only be the number
            # of blocks rather than size in bytes.
            attrs['size'] = \
                str(read_sys_block_size_bytes(device['DEVNAME']))
            blockdev[device['DEVNAME']] = dict(device)
            blockdev[device['DEVNAME']].update({'attrs': attrs})
            # include partition table info if present
            ptable = _extract_partition_table(device['DEVNAME'])
            if ptable:
                blockdev[device['DEVNAME']].update(ptable)

    return blockdev


class Storage():
    """ The Storage class includes a map of storage types that
        probert knows how to extract required information needed
        for installation and use.  Each storage module included
        provides a probe method which will prepare and probe the
        environment for the specific type of storage devices.

        The result of each probe is collected into a dictionary
        which is collected in the class .results attribute.

        The probe is non-destructive and read-only; however a
        probe module may load additional modules if they are not
        present.
    """
    probe_map = {
        'bcache': bcache.probe,
        'blockdev': blockdev_probe,
        'dasd': dasd.probe,
        'dmcrypt': dmcrypt.probe,
        'filesystem': filesystem.probe,
        'lvm': lvm.probe,
        'mount': mount.probe,
        'multipath': multipath.probe,
        'os': os.probe,
        'raid': raid.probe,
        'zfs': zfs.probe
    }

    def __init__(self, results={}):
        self.results = results
        self.context = pyudev.Context()

    def _get_probe_types(self):
        return {ptype for ptype, pfunc in self.probe_map.items() if pfunc}

    def probe(self, probe_types=None):
        default_probes = self._get_probe_types()
        if not probe_types:
            to_probe = default_probes
        else:
            to_probe = probe_types.intersection(default_probes)

        if len(to_probe) == 0:
            not_avail = probe_types.difference(default_probes)
            print('Requsted probes not available: %s' % probe_types)
            print('Valid probe types: %s' % default_probes)
            print('Unavilable probe types: %s' % not_avail)
            return self.results

        probed_data = {}
        for ptype in to_probe:
            pfunc = self.probe_map[ptype]
            probed_data[ptype] = pfunc(context=self.context)

        self.results = probed_data
        return probed_data
