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
import subprocess

import pyudev

from probert.utils import (
    read_sys_block_size_bytes,
    sane_block_devices,
    )


log = logging.getLogger('probert.raid')

SUPPORTED_RAID_TYPES = ['raid0', 'raid1', 'raid5', 'raid6', 'raid10']


def mdadm_assemble(scan=True, ignore_errors=True):
    cmd = ['mdadm', '--detail', '--scan', '-v']
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        log.error('Failed mdadm_assemble command %s: %s', cmd, e)
    except FileNotFoundError as e:
        log.error('Failed mdadm_assemble, mdadm command not found: %s', e)

    return


def get_mdadm_array_spares(md_device, detail):

    def role_key_to_dev(rolekey):
        # MD_DEVICE_dev_dm_5_ROLE=spare -> MD_DEVICE_dev_dm_5_DEV
        devname_mangled = rolekey.split('MD_DEVICE_')[1].split('_ROLE')[0]
        return 'MD_DEVICE_%s_DEV' % devname_mangled

    def keymatch(key, data, role):
        prefix = key.startswith('MD_DEVICE_')
        suffix = key.endswith('_ROLE')
        matches = data.get(key) == role
        return (prefix and suffix and matches)

    def get_dev_from_key(key, data):
        return data.get(role_key_to_dev(key))

    return [get_dev_from_key(key, detail) for key in detail.keys()
            if keymatch(key, detail, 'spare')]


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


def probe(context=None, report=False):
    """Initiate an mdadm assemble to awaken existing MDADM devices.
       For each md block device, extract required information needed
       to describe the array for recreation or reuse as needed.

       mdadm tooling provides information about the raid type,
       the members, the size, the name, uuids, metadata version.
    """
    mdadm_assemble()

    # ignore passed context, must read udev after assembling mdadm devices
    context = pyudev.Context()

    raids = {}
    for device in sane_block_devices(context):
        if device.get('DEVTYPE') != 'disk':
            continue
        devname = device['DEVNAME']
        if 'MD_NAME' in device or device.get('MD_METADATA') == 'imsm':
            devices, spares = get_mdadm_array_members(devname, device)
            cfg = dict(device)
            if device.get('MD_METADATA') == 'imsm':
                # All disks in a imsm container show up as spares, in some
                # sense because they are not "used" by the container (there is
                # a concept of a spare drive in a container -- where there is a
                # drive in the container that is not part of a volume/subarray
                # within it -- but this is a fairly ephemeral concept which
                # doesn't survive a reboot, so we don't account for that
                # here). We don't care about that though and just record all
                # component disks as active.
                devices = devices + spares
                spares = []
            cfg.update({
                'raidlevel': device['MD_LEVEL'],
                'devices': devices,
                'spare_devices': spares,
                'size': str(read_sys_block_size_bytes(devname)),
                })
            raids[devname] = cfg
        elif 'MD_CONTAINER' in device:
            cfg = dict(device)
            cfg.update({
                'raidlevel': device['MD_LEVEL'],
                'container': device['MD_CONTAINER'],
                'size': str(read_sys_block_size_bytes(devname)),
                })
            raids[devname] = cfg

    return raids
