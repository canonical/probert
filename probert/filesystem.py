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
import pyudev

log = logging.getLogger('probert.filesystems')


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


def get_device_filesystem(device):
    # extract ID_FS_* keys into dict, dropping leading ID_FS
    return {k.replace('ID_FS_', ''): v
            for k, v in device.items() if k.startswith('ID_FS_')}


def probe(context=None):
    filesystems = {}
    supported_fs = get_supported_filesystems()
    if not context:
        context = pyudev.Context()

    for device in context.list_devices(subsystem='block'):
        if device['MAJOR'] not in ["1", "7"]:
            fs_info = get_device_filesystem(device)
            if fs_info and fs_info['TYPE'] in supported_fs:
                filesystems[device['DEVNAME']] = fs_info

    return filesystems
