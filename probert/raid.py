# Copyright 2019 Canonical, Ltd.
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

import logging
import pyudev
import subprocess

from probert.utils import (read_sys_block_size,
                           read_sys_block_slaves,
                           udev_get_attributes)

log = logging.getLogger('probert.raid')

SUPPORTED_RAID_TYPES = ['raid0', 'raid1', 'raid5', 'raid6', 'raid10']


def mdadm_assemble(scan=True, ignore_errors=True):
    cmd = ['mdadm', '--detail', '--scan', '-v']
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        log.error('Failed mdadm_assemble command %s: %s', cmd, e)

    return


def get_mdadm_array_members(md_device, detail):

    md_devices = int(detail.get('MD_DEVICES'))
    md_device_keys = [key for key in detail.keys()
                      if key.startswith('MD_DEVICE_') and key.endswith('_DEV')]
    if len(md_device_keys) != md_devices:
        log.warning('mdadm: mismatch on expected number of array members:'
                    ' device(%s) expected(%s) found(%s)',
                    md_device, md_devices, len(md_device_keys))

    expected_devices = sorted(['/dev/' + dev
                               for dev in read_sys_block_slaves(md_device)])
    found_devices = sorted([detail[key] for key in md_device_keys])
    if found_devices != expected_devices:
        log.warning('mdadm: mismatch on expected array members:'
                    ' device(%s) expected(%s) != found(%s)',
                    md_device, expected_devices, found_devices)

    return found_devices


def extract_mdadm_raid_name(conf):
    raid_name = conf.get('MD_NAME')
    if ':' in raid_name:
        _, raid_name = raid_name.split(':')
    return raid_name


def as_config(devname, conf):
    if conf.get('MD_LEVEL') in SUPPORTED_RAID_TYPES:
        raid_name = extract_mdadm_raid_name(conf)
        return {'id': 'mdadm-%s' % raid_name,
                'type': 'raid',
                'name': raid_name,
                'raidlevel': conf.get('MD_LEVEL'),
                'devices': get_mdadm_array_members(devname, conf),
                'spare_devices': None}

    return None


class MDADM():
    def __init__(self, results={}):
        self.results = results
        self.context = None

    def probe(self, report=False):
        mdadm_assemble()

        # read udev afte probing
        self.context = pyudev.Context()

        raids = {}
        for device in self.context.list_devices(subsystem='block'):
            if 'MD_NAME' in device:
                devname = device['DEVNAME']
                attrs = udev_get_attributes(device)
                attrs['size'] = str(read_sys_block_size(devname))
                raids[devname] = dict(device)

        self.results = {'raid': raids}
        return self.results

    def export(self):
        raids = []
        raid_config = self.results.get('raid', {})
        for devname, conf in raid_config.items():
            cfg = as_config(devname, conf)
            if cfg:
                raids.append(cfg)

        return {'version': 1, 'config': raids}
