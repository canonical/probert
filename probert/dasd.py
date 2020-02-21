# Copyright 2020 Canonical, Ltd.
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
import re
import subprocess

log = logging.getLogger('probert.dasd')

DASD_FORMAT = r"^format\s+:.+\s+(?P<format>\w+\s\w+)$"
DASD_BLKSIZE = r"^blocksize\s+:\shex\s\w+\s+dec\s(?P<blksize>\d+)$"


def _search(regex, content, groupkey, flags=None):
    if flags is None:
        flags = re.MULTILINE
    m = re.search(regex, content, flags)
    if m:
        return m.group(groupkey)


def blocksize(dasdview_output):
    """ Read and return device_id's 'blocksize' value.

    :param: device_id: string of device ccw bus_id.
    :returns: int: the device's current blocksize.
    """
    if not dasdview_output:
        return

    blksize = _search(DASD_BLKSIZE, dasdview_output, 'blksize')
    if blksize:
        return int(blksize)


def disk_format(dasdview_output):
    """ Read and return specified device "disk_layout" value.

    :returns: string: One of ['cdl', 'ldl', 'not-formatted'].
    :raises: ValueError if dasdview result missing 'format' section.

    """
    if not dasdview_output:
        return

    mapping = {
       'cdl formatted': 'cdl',
       'ldl formatted': 'ldl',
       'not formatted': 'not-formatted',
    }
    diskfmt = _search(DASD_FORMAT, dasdview_output, 'format')
    if diskfmt:
        return mapping.get(diskfmt.lower())


def dasdview(devname):
    ''' Run dasdview on devname and return dictionary of data.

    dasdview --extended has 3 sections
    general (2:6), geometry (8:12), extended (14:)

    '''
    if not os.path.exists(devname):
        raise ValueError("Invalid dasd device name: '%s'" % devname)

    cmd = ['dasdview', '--extended', devname]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.error('Failed to run cmd: %s', cmd)
        return None

    return result.stdout.decode('utf-8')


def get_dasd_info(device):
    """ from a udev blockdev device entry, return all required dasd info

    """
    name = device.get('DEVNAME')
    device_id = device.get('ID_PATH', '').replace('ccw-', '')
    dasdview_output = dasdview(name)
    diskfmt = disk_format(dasdview_output)
    blksize = blocksize(dasdview_output)
    if not all([name, device_id, diskfmt, blksize]):
        vals = ("name=%s device_id=%s format=%s blksize=%s" % (
                name, device_id, diskfmt, blksize))
        log.debug('Failed to probe some DASD values: %s', vals)
        return None

    return {'name': name, 'device_id': device_id,
            'disk_layout': diskfmt, 'blocksize': blksize}


def probe(context=None):
    """Examine all dasd devices present and extract configuration attributes

       This data is useful for determining if the dasd device has been
       formatted, if so what the block size, the partition layout used
       and the s390x device_id used to uniquely identify the device.
    """
    log.debug('Probing DASD devies')
    dasds = {}
    if not context:
        context = pyudev.Context()

    for device in context.list_devices(subsystem='block'):
        # dasd devices have MAJOR 95
        if device['MAJOR'] != "94":
            continue
        # ignore dasd partitions
        if 'PARTN' in device:
            continue
        dasd_info = get_dasd_info(device)
        if dasd_info:
            dasds[device['DEVNAME']] = dasd_info

    return dasds
