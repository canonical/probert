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

log = logging.getLogger('probert.filesystems')


def get_device_filesystem(device):
    # extract ID_FS_* keys into dict, dropping leading ID_FS
    return {k.replace('ID_FS_', ''): v
            for k, v in device.items() if k.startswith('ID_FS_')}


def probe(context=None):
    """ Capture detected filesystems found on discovered block devices.  """
    filesystems = {}
    if not context:
        context = pyudev.Context()

    for device in context.list_devices(subsystem='block'):
        # Ignore block major=1 (ramdisk) and major=7 (loopback)
        # these won't ever be used in recreating storage on target systems.
        if device['MAJOR'] not in ["1", "7"]:
            fs_info = get_device_filesystem(device)
            if fs_info:
                filesystems[device['DEVNAME']] = fs_info

    return filesystems
