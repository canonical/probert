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

import logging
import subprocess

import pyudev

from probert.utils import sane_block_devices


log = logging.getLogger('probert.dmcrypt')


def dmsetup_info(devname):
    ''' returns dict of info about device mapper dev.

    {'blkdevname': 'dm-0',
     'blkdevs_used': 'sda5',
     'name': 'sda5_crypt',
     'subsystem': 'CRYPT',
     'uuid': 'CRYPT-LUKS1-2b370697149743b0b2407d11f88311f1-sda5_crypt'
    }
    '''
    _SEP = '='
    fields = ('name,uuid,blkdevname,blkdevs_used,subsystem'.split(','))
    try:
        output = subprocess.check_output(
            ['sudo', 'dmsetup', 'info', devname, '-C', '-o',
             ','.join(fields), '--noheading', '--separator', _SEP])
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe dmsetup info:', e)
        return None
    values = output.decode('utf-8').strip().split(_SEP)
    info = dict(zip(fields, values))
    return info


def probe(context=None, report=False):
    """ Probing for dm_crypt devices requires running dmsetup info commands
        to collect how a particular dm-X device is composed.
    """
    # ignore supplied context, we need to read udev after scan/vgchange
    context = pyudev.Context()

    crypt_devices = {}

    # look for block devices with DM_UUID and CRYPT; these are crypt devices
    for device in sane_block_devices(context):
        if 'DM_UUID' in device and device['DM_UUID'].startswith('CRYPT'):
            devname = device['DEVNAME']
            dm_info = dmsetup_info(devname)
            crypt_devices[dm_info['name']] = dm_info

    return crypt_devices
