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
import os
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


def get_mdadm_array_members(md_device):
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
    cmd = ['mdadm', '--detail', '--export', md_device]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        output = result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        log.error('failed to get detail for %s: %s', md_device, e)
        return ([], [])

    devices = {}
    roles = {}

    for line in output.splitlines():
        line = line.strip()
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        if k.startswith('MD_DEVICE_'):
            if k.endswith("_DEV"):
                dev_key = k[len('MD_DEVICE_'):-len('_DEV')]
                devices[dev_key] = v
            elif k.endswith("_ROLE"):
                dev_key = k[len('MD_DEVICE_'):-len('_ROLE')]
                roles[dev_key] = v

    actives = []
    spares = []

    for dev_key, devname in devices.items():
        if roles.get(dev_key) == 'spare':
            spares.append(devname)
        else:
            actives.append(devname)
    return (sorted(actives), sorted(spares))


async def probe(context=None, report=False, **kw):
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
        if not os.path.basename(devname).startswith('md'):
            continue
        if 'MD_CONTAINER' in device:
            cfg = dict(device)
            cfg.update({
                'container': device['MD_CONTAINER'],
                'size': str(read_sys_block_size_bytes(devname)),
                })
            if 'MD_LEVEL' in device:
                cfg.update({
                    'raidlevel': device['MD_LEVEL'],
                })
            raids[devname] = cfg
        else:
            devices, spares = get_mdadm_array_members(devname)
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
                'devices': devices,
                'spare_devices': spares,
                'size': str(read_sys_block_size_bytes(devname)),
                })
            if 'MD_LEVEL' in device:
                cfg.update({
                    'raidlevel': device['MD_LEVEL'],
                })
            raids[devname] = cfg

    return raids
