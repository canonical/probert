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
import platform
import pyudev
import re
import subprocess

log = logging.getLogger('probert.dasd')


def _dasd_view_dec_pattern(label):
    return r"^{}\s+:\shex\s\w+\s+dec\s(?P<value>\d+)$".format(
        re.escape(label))


DASD_FORMAT = r"^format\s+:.+\s+(?P<value>\w+\s\w+)$"
DASD_BLKSIZE = _dasd_view_dec_pattern("blocksize")
DASD_CYLINDERS = _dasd_view_dec_pattern("number of cylinders")
DASD_TRACKS_PER_CYLINDER = _dasd_view_dec_pattern("tracks per cylinder")
DASD_TYPE = r"^type\s+:\s(?P<value>[A-Za-z]+)\s*$"


def find_val(regex, content):
    m = re.search(regex, content, re.MULTILINE)
    if m is not None:
        return m.group("value")


def find_val_int(regex, content):
    v = find_val(regex, content)
    if v is not None:
        return int(v)


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
    diskfmt = find_val(DASD_FORMAT, dasdview_output)
    if diskfmt is not None:
        return mapping.get(diskfmt.lower())


def dasdview(devname):
    ''' Run dasdview on devname and return the output.

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
    blksize = find_val_int(DASD_BLKSIZE, dasdview_output)
    type = find_val(DASD_TYPE, dasdview_output)

    cylinders = find_val_int(DASD_CYLINDERS, dasdview_output)
    tracks_per_cylinder = find_val_int(
        DASD_TRACKS_PER_CYLINDER, dasdview_output)

    if not all([name, device_id, diskfmt, blksize]):
        vals = ("name=%s device_id=%s format=%s blksize=%s" % (
                name, device_id, diskfmt, blksize))
        log.debug('Failed to probe some DASD values: %s', vals)
        return None

    return {
        'blocksize': blksize,
        'cylinders': cylinders,
        'device_id': device_id,
        'disk_layout': diskfmt,
        'name': name,
        'tracks_per_cylinder': tracks_per_cylinder,
        'type': type,
        }


def probe(context=None):
    """Examine all dasd devices present and extract configuration attributes

       This data is useful for determining if the dasd device has been
       formatted, if so what the block size, the partition layout used
       and the s390x device_id used to uniquely identify the device.
    """
    log.debug('Probing DASD devies')
    machine = platform.machine()
    if machine != "s390x":
        log.debug('DASD devices only present on s390x, arch=%s', machine)
        return {}

    dasds = {}
    if not context:
        context = pyudev.Context()

    for device in context.list_devices(subsystem='block'):
        # dasd devices have MAJOR 94
        if device['MAJOR'] != "94":
            continue
        # ignore dasd partitions
        if 'PARTN' in device:
            continue

        try:
            dasd_info = get_dasd_info(device)
        except ValueError as e:
            log.error('Error probing dasd device %s: %s', device['DEVNAME'], e)
            dasd_info = None

        if dasd_info:
            dasds[device['DEVNAME']] = dasd_info

    return dasds
