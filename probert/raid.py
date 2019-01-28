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


def get_mdadm_array_spares(md_device, detail):

    def role_key_to_dev(rolekey):
        # MD_DEVICE_dev_dm_5_ROLE=spare -> MD_DEVICE_dev_dm_5_DEV
        devname_mangled = rolekey.split('MD_DEVICE_')[1].split('_ROLE')[0]
        return 'MD_DEVICE_%s_DEV' % devname_mangled

    return [detail[role_key_to_dev(key)]
            for key in detail.keys() if key.startswith('MD_DEVICE_') and
            key.endswith('_ROLE') and detail[key] == 'spare']


def get_mdadm_array_members(md_device, detail):
    ''' extract array devices and spares from mdadm --detail --export output

    MD_LEVEL=raid5
    MD_DEVICES=3
    MD_METADATA=1.2
    MD_UUID=7fe1895e:34dcb6dc:d1bcbb9c:f3e05134
    MD_NAME=s1lp6:raid5-2406-2407-2408-2409
    MD_DEVICE_ev_dm_5_ROLE=spare
    MD_DEVICE_ev_dm_5_DEV=/dev/dm-5
    MD_DEVICE_ev_dm_3_ROLE=1
    MD_DEVICE_ev_dm_3_DEV=/dev/dm-3
    MD_DEVICE_ev_dm_4_ROLE=2
    MD_DEVICE_ev_dm_4_DEV=/dev/dm-4
    MD_DEVICE_ev_dm_2_ROLE=0
    MD_DEVICE_ev_dm_2_DEV=/dev/dm-2

    returns (['/dev/dm2', '/dev/dm-3', '/dev/dm-4'], ['/dev/dm-5'])
    '''
    md_device_keys = [key for key in detail.keys()
                      if key.startswith('MD_DEVICE_') and key.endswith('_DEV')]
    spares = sorted(get_mdadm_array_spares(md_device, detail))
    devices = sorted([detail[key] for key in md_device_keys
                      if detail[key] not in spares])
    return (devices, spares)


def extract_mdadm_raid_name(conf):
    ''' return the raid array name, removing homehost if present.

    MD_NAME=s1lp6:raid5-2406-2407-2408-2409

    returns 'raid5-2406-2407-2408-2409'
    '''
    raid_name = conf.get('MD_NAME')
    if ':' in raid_name:
        _, raid_name = raid_name.split(':')
    return raid_name


def as_config(devname, conf):
    if conf.get('MD_LEVEL') in SUPPORTED_RAID_TYPES:
        raid_name = extract_mdadm_raid_name(conf)
        devices, spares = get_mdadm_array_members(devname, conf)
        return {'id': 'mdadm-%s' % raid_name,
                'type': 'raid',
                'name': raid_name,
                'raidlevel': conf.get('MD_LEVEL'),
                'devices': devices,
                'spare_devices': spares}

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

        self.results = raids
        return self.results

    def export(self):
        raids = []
        for devname, conf in self.results.items():
            cfg = as_config(devname, conf)
            if cfg:
                raids.append(cfg)

        return {'version': 1, 'config': raids}
