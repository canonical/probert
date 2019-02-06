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

from collections import namedtuple
import logging
import os
import stat
import pyudev

log = logging.getLogger('probert.filesystems')
MountEntry = namedtuple("MountEntry", ('device', 'realpath', 'mountpoint',
                                       'fstype', 'options', 'freq', 'passno'))
MountEntry.__new__.__defaults__ = (None, None, None, None, '', '0', '0')


def get_supported_filesystems():
    """ Return a list of filesystems that the kernel currently supports
        as read from /proc/filesystems.

        Raises RuntimeError if /proc/filesystems does not exist.
    """
    proc_fs = "/proc/filesystems"
    if not os.path.exists(proc_fs):
        raise RuntimeError("Unable to read 'filesystems' from %s" % proc_fs)

    with open(proc_fs, 'r') as fh:
        proc_fs_contents = fh.read()

    return [l.split('\t')[1].strip()
            for l in proc_fs_contents.splitlines()]


def read_proc_mounts():
    with open("/proc/mounts", "r") as fp:
        return fp.read()


def get_block_mounts(proc_mounts=None):
    # return mount entry if device is in /proc/mounts

    def is_blockdev(path):
        return os.path.exists(path) and stat.S_ISBLK(os.stat(path).st_mode)

    if not proc_mounts:
        proc_mounts = read_proc_mounts()

    block_mounts = {}
    for line in proc_mounts.splitlines():
        dev, mp, fs, opts, freq, passno = line.split()
        # /proc/mounts device entry may be a symlink, resolve it
        realpath = os.path.realpath(dev)
        if not is_blockdev(realpath):
            continue

        entry = MountEntry(dev, realpath, mp, fs, opts, freq, passno)
        if entry.realpath not in block_mounts:
            block_mounts[entry.realpath] = [entry]
        else:
            block_mounts[entry.realpath].append(entry)

    return block_mounts


def mountentry_asdict(mount):
    return {'mountpoint': mount.mountpoint,
            'fstype': mount.fstype,
            'options': mount.options,
            'realpath': mount.realpath,
            'device': mount.device}


def probe(context=None):
    supported_fs = get_supported_filesystems()
    if not context:
        context = pyudev.Context()

    blockdev_mounts = get_block_mounts()
    mounts = {}
    for device in context.list_devices(subsystem='block'):
        if device['MAJOR'] not in ["1", "7"]:
            devname = device['DEVNAME']
            if devname in blockdev_mounts:
                for mount in blockdev_mounts[devname]:
                    if mount.fstype not in supported_fs:
                        continue

                    if mount.device in mounts:
                        mounts[mount.device].append(mountentry_asdict(mount))
                    else:
                        mounts[mount.device] = [mountentry_asdict(mount)]

    return mounts
