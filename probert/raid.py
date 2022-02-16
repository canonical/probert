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

import glob
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


def get_mdadm_array_members(device):
    '''extract array devices and spares from sysfs.

    See https://docs.kernel.org/admin-guide/md.html#md-devices-in-sysfs
    for hints.
    '''
    devices = []
    spares = []
    block_links = glob.glob(os.path.join(device.sys_path, 'md/dev-*/block'))
    for block_link in block_links:
        member_devname = '/dev/' + os.path.basename(os.readlink(block_link))
        state_file = os.path.join(os.path.dirname(block_link), 'state')
        with open(state_file) as fp:
            state = fp.read().strip()
        if state == 'spare':
            spares.append(member_devname)
        else:
            devices.append(member_devname)
    return (devices, spares)


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
        if not os.path.exists(os.path.join(device.sys_path, 'md')):
            continue
        devname = device['DEVNAME']
        if 'MD_CONTAINER' in device:
            cfg = dict(device)
            cfg.update({
                'raidlevel': device['MD_LEVEL'],
                'container': device['MD_CONTAINER'],
                'size': str(read_sys_block_size_bytes(devname)),
                })
            raids[devname] = cfg
        else:
            devices, spares = get_mdadm_array_members(device)
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

    return raids
