# Copyright 2019 Canonical, Ltd.
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

import asyncio
import logging
import re
import shutil

import pyudev

from probert.utils import (
    arun,
    sane_block_devices,
)

log = logging.getLogger('probert.filesystems')


async def get_dumpe2fs_info(path):
    ret = {}
    dumpe2fs = shutil.which('dumpe2fs')
    if dumpe2fs is None:
        log.debug('ext volume size not found: dumpe2fs not found')
        return None
    out = await arun([dumpe2fs, '-h', path])
    if out is None:
        log.debug('ext volume size not found: dumpe2fs failure')
        return None
    # Block count:              20480
    # Block size:               4096
    block_count_matcher = re.compile(r'^Block count:\s+(\d+)$')
    block_size_matcher = re.compile(r'^Block size:\s+(\d+)$')
    for line in out.splitlines():
        m = block_count_matcher.fullmatch(line)
        if m:
            ret['block_count'] = int(m.group(1))
        m = block_size_matcher.fullmatch(line)
        if m:
            ret['block_size'] = int(m.group(1))
    if 'block_count' not in ret or 'block_size' not in ret:
        log.debug('ext volume size not found: unexpected output format')
        return None
    return ret


async def get_resize2fs_info(path):
    # Estimated minimum size of the filesystem: 1696
    resize2fs = shutil.which('resize2fs')
    if resize2fs is None:
        log.debug('ext volume size not found: resize2fs not found')
        return None
    out = await arun([resize2fs, '-P', path])
    if out is None:
        return None
    min_blocks_matcher = re.compile(
        r'^Estimated minimum size of the filesystem: (\d+)$')
    for line in out.splitlines():
        m = min_blocks_matcher.fullmatch(line)
        if m:
            return {'min_blocks': int(m.group(1))}
    return None


async def get_ext_sizing(device):
    path = device.device_node
    dumpe2fs_info = await get_dumpe2fs_info(path)
    if not dumpe2fs_info:
        return None
    ret = {'SIZE': dumpe2fs_info['block_count'] * dumpe2fs_info['block_size']}

    resize2fs_info = await get_resize2fs_info(path)
    if resize2fs_info:
        min_size = resize2fs_info['min_blocks'] * dumpe2fs_info['block_size']
        ret['ESTIMATED_MIN_SIZE'] = min_size
    return ret


async def get_ntfs_sizing(device):
    path = device.device_node
    ntfsresize = shutil.which('ntfsresize')
    if ntfsresize is None:
        log.debug('ntfs volume size not found: ntfsresize not found')
        return None
    cmd = [ntfsresize,
           '--no-action',
           '--force',  # needed post-resize, which otherwise demands a CHKDSK
           '--no-progress-bar',
           '--info', path]
    out = await arun(cmd)
    if out is None:
        log.debug('ntfs volume size not found: ntfsresize failure')
        return None
    # Sample input:
    #   Current volume size: 41939456 bytes (42 MB)
    #   ...
    #   You might resize at 2613248 bytes or 3 MB (freeing 39 MB).
    #   or
    #   ERROR: Volume is full. To shrink it, delete unused files.
    volsize_matcher = re.compile(r'^Current volume size: ([0-9]+) bytes')
    minsize_matcher = re.compile(r'^You might resize at ([0-9]+) bytes')
    volfull_matcher = re.compile(r'^ERROR: Volume is full.')
    ret = {}
    is_full = False
    for line in out.splitlines():
        m = volsize_matcher.match(line)
        if m:
            ret['SIZE'] = int(m.group(1))
        m = minsize_matcher.match(line)
        if m:
            ret['ESTIMATED_MIN_SIZE'] = int(m.group(1))
        m = volfull_matcher.match(line)
        if m:
            is_full = True
    if 'SIZE' not in ret:
        log.debug('ntfs volume size not found: unexpected output format')
        return None
    if is_full:
        ret['ESTIMATED_MIN_SIZE'] = ret['SIZE']
    return ret


async def get_swap_sizing(device):
    if 'ID_PART_ENTRY_SIZE' in device:
        size = int(device['ID_PART_ENTRY_SIZE']) * 512
    else:
        size = int(device.get('attrs', {}).get('size', 0))
    if not size:
        log.debug(
            'swap volume size not found. Neither ID_PART_ENTRY_SIZE nor'
            ' attrs:size present'
        )
        return None
    return {'SIZE': size, 'ESTIMATED_MIN_SIZE': 0}


sizing_tools = {
    'ext2': get_ext_sizing,
    'ext3': get_ext_sizing,
    'ext4': get_ext_sizing,
    'ntfs': get_ntfs_sizing,
    'swap': get_swap_sizing,
}


async def get_device_filesystem(device, sizing):
    # extract ID_FS_* keys into dict, dropping leading ID_FS
    # This may look like a stupid way to iterate over a dictionary-like
    # collection. However, iterating over device.properties.items() will fail
    # if any of the values is not utf-8 (or whatever the system's encoding is).
    # We have had multiple reports of PARTNAME being invalid utf-8.
    # See LP: 2017862
    keys = [key for key in device.properties if key.startswith('ID_FS_')]
    fs_info = {k.replace('ID_FS_', ''): device.properties[k] for k in keys}

    if sizing:
        fstype = fs_info.get('TYPE', None)
        if fstype in sizing_tools:
            size_info = await sizing_tools[fstype](device)
            if size_info is not None:
                fs_info.update(size_info)
        fs_info.setdefault('ESTIMATED_MIN_SIZE', -1)
    return fs_info


async def probe(context=None, enabled_probes=None, *, parallelize=False, **kw):
    """ Capture detected filesystems found on discovered block devices.  """
    filesystems = {}
    if not context:
        context = pyudev.Context()

    need_fs_sizing = 'filesystem_sizing' in enabled_probes

    async def probe_filesystem(device):
        # Ignore block major=1 (ramdisk) and major=7 (loopback)
        # these won't ever be used in recreating storage on target systems.
        if device['MAJOR'] not in ["1", "7"]:
            fs_info = await get_device_filesystem(device, need_fs_sizing)
            # The ID_FS_ udev values come from libblkid, which contains code to
            # recognize lots of different things that block devices or their
            # partitions can contain (filesystems, lvm PVs, bcache, ...).  We
            # only want to report things that are mountable filesystems here,
            # which libblkid conveniently tags with ID_FS_USAGE=filesystem.
            # Swap is a bit of a special case because it is not a mountable
            # filesystem in the usual sense, but subiquity still needs to
            # generate mount actions for it.  Crypto is a disguised filesystem.
            if fs_info.get("USAGE") in ("filesystem", "crypto") or \
               fs_info.get("TYPE") == "swap":
                filesystems[device['DEVNAME']] = fs_info

    coroutines = [probe_filesystem(dev) for dev in sane_block_devices(context)]

    if parallelize:
        await asyncio.gather(*coroutines)
    else:
        for coroutine in coroutines:
            await coroutine

    return filesystems
