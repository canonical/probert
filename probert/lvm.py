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
import json
import pyudev
import subprocess

from probert.storage import read_sys_block_size

log = logging.getLogger('probert.lvm')


class LvInfo():
    def __init__(self, lvname, vgname, lvsize):
        self.type = 'lvm_partition'
        self.name = lvname
        self.vgname = vgname
        self.size = lvsize
        self.fullname = "%s/%s" % (self.name, self.vgname)
        self.id = 'lvmpart-%s' % self.name

    def as_config(self):
        return {
            'id': self.id,
            'name': self.name,
            'size': self.size,
            'type': self.type,
            'volgroup': 'lvm_volgroup-%s' % self.volgroup
        }


class VgInfo():
    def __init__(self, name, devices):
        self.type = 'lvm_volgroup'
        self.name = name
        self.devices = devices
        self.id = 'lvmvol-%s' % (self.name)

    def as_config(self):
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'devices': self.devices,
        }


class PvInfo():
    def __init__(self, name, devpath):
        self.type = 'lvm_physdev'
        self.name = name
        self.devpath = devpath
        self.id = 'lvmphysdev-%s' % self.name

    def as_config(self):
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'devpath': self.devpath
        }


def probe_lvm_report():
    try:
        output, _err = subprocess.check_output(['lvm', 'fullreport',
                                                '--nosufix', '--units', 'B',
                                                '--reportformat', 'json'])
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe LVM devices on system:', e)
        return None

    try:
        lvm_report = json.loads(output)
    except json.decoder.JSONDecodeError as e:
        log.error('Failed to load LVM json report:', e)
        return None

    return lvm_report


def dmsetup_info(devname):
    ''' returns dict of info about device mapper dev.

    {'blkdevname': 'dm-0',
     'blkdevs_used': 'sdbr,sdbq,sdbp',
     'lv_name': 'lv_srv',
     'subsystem': 'LVM',
     'uuid': 'LVM-lyrZxQgOcgVSlj81LvyUnvq4DW3uLLrfJLI5ieYZR9a2fSOGBK03KM78',
     'vg_name': 'storage_vg_242x'}
    '''
    _SEP = '='
    fields = (
        'subsystem,vg_name,lv_name,blkdevname,uuid,blkdevs_used'.split(','))
    try:
        output = subprocess.check_output(
            ['sudo', 'dmsetup', 'info', devname, '-C', '-o', fields,
             '--noheading', '--separator', _SEP])
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe dmsetup info:', e)
        return None
    values = output.decode('utf-8').strip().split(_SEP)
    info = dict(zip(fields, values))
    return info


class LVM():
    def __init__(self, results={}):
        self.results = results
        self.context = pyudev.Context()

    def probe(self):
        lvols = []
        vgroups = []
        pvols = []
        report = probe_lvm_report()
        for device in self.context.list_devices(subsystem='block'):
            if 'DM_UUID' in device and device['DM_UUID'].startswith('LVM'):
                # dm_info = dmsetup_info(device['DEVNAME'])
                new_lv = {
                    'lv_full_name': '%s/%s' % (device['DM_VG_NAME'],
                                               device['DM_LV_NAME']),
                    'lv_size': read_sys_block_size(device['DEVNAME']),
                }
                lvols.append(new_lv)

        storage = {
            'lvm': {
                'lvs': lvols, 'vgs': vgroups, 'pvs': pvols,
                'report': report,
            }
        }
        self.results = storage
