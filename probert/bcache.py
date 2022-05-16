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

log = logging.getLogger('probert.bcache')


def superblock_asdict(device=None, data=None):
    """ Convert output from bcache-super-show into a dictionary"""

    if not device and not data:
        raise ValueError('Supply a device name, or data to parse')

    if not data:
        cmd = ['bcache-super-show', device]
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        data = result.stdout.decode('utf-8')
    bcache_super = {}
    for line in data.splitlines():
        if not line:
            continue
        values = [val for val in line.split('\t') if val]
        if len(values) == 2:
            bcache_super.update({values[0]: values[1]})

    return bcache_super


def parse_sb_version(sb_version):
    """ Convert sb_version string to integer if possible"""
    try:
        # 'sb.version': '1 [backing device]'
        # 'sb.version': '3 [caching device]'
        version = int(sb_version.split()[0])
    except (AttributeError, ValueError):
        log.warning("Failed to parse bcache 'sb.version' field"
                    " as integer: %s", sb_version)
        return None

    return version


def is_backing(device):
    """ Test if device is a bcache backing device

    A runtime check for an active bcache backing device is to
    examine /sys/class/block/<kname>/bcache/label

    However if a device is not active then read the superblock
    of the device and check that sb.version == 1"""

    sys_block = '/sys/class/block/%s' % os.path.basename(device)
    bcache_sys_attr = os.path.join(sys_block, 'bcache', 'label')
    return os.path.exists(bcache_sys_attr)


def is_caching(device):
    """ Test if device is a bcache caching device

    A runtime check for an active bcache backing device is to
    examine /sys/class/block/<kname>/bcache/cache_replacement_policy

    However if a device is not active then read the superblock
    of the device and check that sb.version == 3"""

    sys_block = '/sys/class/block/%s' % os.path.basename(device)
    bcache_sys_attr = os.path.join(sys_block, 'bcache',
                                   'cache_replacement_policy')
    return os.path.exists(bcache_sys_attr)


def is_bcache_device(device):
    return device.get('ID_FS_TYPE') == 'bcache'


def probe(context=None, **kw):
    """Probe the system for bcache devices.  Bcache devices
       are registered with the kernel upon module load and when
       devices are hot/cold plugged.  There are two portions to
       a bcache, the backing device which holds data and the cache
       device which cached data from the backing device.  A backing
       device encodes a specific cache_set UUID in the backing device
       which is used to bind both device in the kernel and create a
       new block device, bcacheN.

       For each block device which has a bcache superblock embedded,
       extract and examine the superblock to determine which type of
       bcache device (backing, caching) and the relevant UUIDs and
       build (if possible) the pairing of caches to backing.

       This probe reports the devices separately but enough information
       is included to re-assemble joined bcache devices if desired.
    """
    backing = {}
    caching = {}
    bcache = {'backing': backing, 'caching': caching}
    if not context:
        return bcache

    for device in context.list_devices(subsystem='block'):
        if is_bcache_device(device):
            devpath = device['DEVNAME']
            sb = superblock_asdict(devpath)
            bkey = sb.get('dev.uuid', 'not available')
            bconfig = {'blockdev': devpath, 'superblock': sb}
            if is_backing(devpath):
                backing[bkey] = bconfig
            elif is_caching(devpath):
                caching[bkey] = bconfig
            else:
                log.error('bcache.probe: %s is not bcache' % devpath)

    return bcache
