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

import asyncio
from dataclasses import dataclass
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
                     nvme, os, raid, zfs)

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


def interesting_storage_devs(context):
    skip_majors = (
        '1',  # ignore ram disks
        '7',  # ignore loopback devices
    )

    for device in sane_block_devices(context):
        if device['MAJOR'] in skip_majors:
            continue
        major, minor = device.get('ID_PART_ENTRY_DISK', '0:0').split(':')
        if major in skip_majors:
            # also skip partitions that are on a device we don't want
            continue
        yield device


async def blockdev_probe(context=None, **kw):
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
    for device in interesting_storage_devs(context):
        devname = device.properties['DEVNAME']
        attrs = udev_get_attributes(device)
        # update the size attr as it may only be the number
        # of blocks rather than size in bytes.
        attrs['size'] = \
            str(read_sys_block_size_bytes(devname))
        # When dereferencing device[prop], pyudev calls bytes.decode(), which
        # can fail if the value is invalid utf-8. We don't want a single
        # invalid value to completely prevent probing. So we iterate
        # over each value manually and ignore those which are invalid.  We know
        # that PARTNAME is subject to failures when accents and other special
        # characters are used in a GPT partition name.
        # See LP: 2017862
        blockdev[devname] = {}
        for prop in device.properties:
            try:
                blockdev[devname][prop] = device.properties[prop]
            except UnicodeDecodeError:
                log.warning('ignoring property %s of device %s because it is'
                            ' not valid utf-8', prop, devname)
        blockdev[devname].update({'attrs': attrs})
        # include partition table info if present
        ptable = _extract_partition_table(devname)
        if ptable:
            blockdev[devname].update(ptable)

    return blockdev


@dataclass
class Probe:
    pfunc: callable
    in_default_set: bool = True


async def null_probe(context=None, **kw):
    """Some probe types are flags that change the behavior of other probes.
       These flag probes do nothing on their own."""
    return None


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
        'bcache': Probe(bcache.probe),
        'blockdev': Probe(blockdev_probe),
        'dasd': Probe(dasd.probe),
        'dmcrypt': Probe(dmcrypt.probe),
        'filesystem': Probe(filesystem.probe),
        'lvm': Probe(lvm.probe),
        'mount': Probe(mount.probe),
        'multipath': Probe(multipath.probe),
        'nvme': Probe(nvme.probe),
        'os': Probe(os.probe, in_default_set=False),
        'filesystem_sizing': Probe(null_probe, in_default_set=False),
        'raid': Probe(raid.probe),
        'zfs': Probe(zfs.probe),
    }

    def __init__(self, results={}):
        self.results = results
        self.context = pyudev.Context()

    def _get_probe_types(self, get_all=False):
        return {ptype for ptype, probe in self.probe_map.items()
                if get_all or probe.in_default_set}

    async def probe(self, probe_types=None, *, parallelize=False):
        default_probes = self._get_probe_types(False)
        all_probes = self._get_probe_types(True)
        if not probe_types:
            to_probe = default_probes
        else:
            if 'defaults' in probe_types:
                probe_types.remove('defaults')
                probe_types = probe_types.union(default_probes)
            to_probe = probe_types.intersection(all_probes)

        if len(to_probe) == 0:
            not_avail = probe_types.difference(all_probes)
            print('Requsted probes not available: %s' % probe_types)
            print('Valid probe types: %s' % all_probes)
            print('Unavilable probe types: %s' % not_avail)
            return self.results

        probed_data = {}

        async def run_probe(ptype):
            probe = self.probe_map[ptype]
            result = await probe.pfunc(context=self.context,
                                       enabled_probes=to_probe,
                                       parallelize=parallelize)
            if result is not None:
                probed_data[ptype] = result

        coroutines = [run_probe(ptype) for ptype in to_probe]

        if parallelize:
            await asyncio.gather(*coroutines)
        else:
            for coroutine in coroutines:
                await coroutine

        self.results = probed_data
        return probed_data
