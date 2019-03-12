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
import os
import pyudev
import subprocess

from probert.utils import read_sys_block_size

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
        cmd = ['lvm', 'fullreport', '--nosuffix', '--units', 'B',
               '--reportformat', 'json']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        output = result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe LVM devices on system:', e)
        return None

    try:
        lvm_report = json.loads(output)
    except json.decoder.JSONDecodeError as e:
        log.error('Failed to load LVM json report:', e)
        return None

    return lvm_report


def _lvm_report(cmd, report_key):
    """ [pvs --reportformat=json -o foo,bar] report_key='pv'
     {
         "report": [
             {
                 "pv": [
                     {"pv_name":"/dev/md0", "vg_name":"vg0",
                      "pv_fmt":"lvm2", "pv_attr":"a--",
                      "pv_size":"<9.99g", "pv_free":"<6.99g"},
                     {"pv_name":"/dev/md1", "vg_name":"vg0",
                      "pv_fmt":"lvm2", "pv_attr":"a--",
                      "pv_size":"<9.99g", "pv_free":"<9.99g"}
                 ]
             }
         ]
     }
    """
    def _flatten_list(data):
        return [y for x in data for y in x]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        output = result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe LVM devices on system:', e)
        return None

    try:
        reports = json.loads(output)
    except json.decoder.JSONDecodeError as e:
        log.error('Failed to load LVM json report:', e)
        return None

    return _flatten_list([report.get(report_key)
                          for report in reports.get('report', [])
                          if report_key in report])


def probe_pvs_report():
    return _lvm_report(['pvs', '--reportformat=json'], 'pv')


def probe_vgs_report():
    report_cmd = ['vgs', '--reportformat=json', '--units=B',
                  '-o', 'vg_name,pv_name,pv_uuid,vg_size']
    return _lvm_report(report_cmd, 'vg')


def probe_lvs_report():
    return _lvm_report('lvs', 'lv')


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
            ['sudo', 'dmsetup', 'info', devname, '-C', '-o',
             ','.join(fields), '--noheading', '--separator', _SEP])
    except subprocess.CalledProcessError as e:
        log.error('Failed to probe dmsetup info:', e)
        return None
    values = output.decode('utf-8').strip().split(_SEP)
    info = dict(zip(fields, values))
    return info


def lvmetad_running():
    return os.path.exists(os.environ.get('LVM_LVMETAD_PIDFILE',
                                         '/run/lvmetad.pid'))


def lvm_scan(activate=True):
    for cmd in [['pvscan'], ['vgscan', '--mknodes']]:
        if lvmetad_running():
            cmd.append('--cache')
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            log.error('Failed lvm_scan command %s: %s', cmd, e)


def activate_volgroups():
    """
    Activate available volgroups and logical volumes within.
    # found
    % vgchange -ay
      1 logical volume(s) in volume group "vg1sdd" now active

    # none found (no output)
    % vgchange -ay
    """

    # vgchange handles syncing with udev by default
    # see man 8 vgchange and flag --noudevsync
    result = subprocess.run(['vgchange', '--activate=y'], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.stdout:
        log.info(result.stdout)


def extract_lvm_partition(probe_data):
    lv_id = "%s/%s" % (probe_data['DM_VG_NAME'], probe_data['DM_LV_NAME'])
    return (
        lv_id, {'fullname': lv_id,
                'name': probe_data['DM_LV_NAME'],
                'volgroup': probe_data['DM_VG_NAME'],
                'size': "%sB" % read_sys_block_size(probe_data['DEVNAME'])})


def extract_lvm_volgroup(probe_data):
    vg_id = probe_data['vg_name']
    return (vg_id, {'name': vg_id,
                    'devices':
                        ['/dev/%s' % d
                         for d in probe_data['blkdevs_used'].split(',')]})


def as_config(lv_type, lvmconf):
    if lv_type == 'vgs':
        return {'id': 'lvmvol-%s' % lvmconf.get('name'),
                'type': 'lvm_volgroup',
                'name': lvmconf.get('name'),
                'devices': lvmconf.get('devices')}
    if lv_type == 'lvs':
        return {'id': 'lvmpart-%s' % lvmconf.get('name'),
                'type': 'lvm_partition',
                'name': lvmconf.get('name'),
                'volgroup': 'lvmvol-%s' % lvmconf.get('volgroup'),
                'size': str(lvmconf.get('size'))}
    return None


def probe(context=None, report=False):
    # scan and activate lvm vgs/lvs
    lvm_scan()
    activate_volgroups()

    # ignore supplied context, we need to read udev after scan/vgchange
    context = pyudev.Context()

    lvols = {}
    vgroups = {}
    pvols = {}
    report = probe_lvm_report() if report else {}
    vg_report = probe_vgs_report()

    for device in context.list_devices(subsystem='block'):
        if 'DM_UUID' in device and device['DM_UUID'].startswith('LVM'):
            (lv_id, new_lv) = extract_lvm_partition(device)
            if lv_id not in lvols:
                lvols[lv_id] = new_lv
            else:
                log.error('Found duplicate logical volume: %s', lv_id)
                continue

            vg_name = device['DM_VG_NAME']
            (vg_id, new_vg) = extract_lvm_volgroup(vg_name, vg_report)
            if vg_id not in vgroups:
                vgroups[vg_id] = new_vg
            else:
                log.error('Found duplicate volume group: %s', vg_id)
                continue

            if vg_id not in pvols:
                pvols[vg_id] = new_vg['devices']

    lvm = {}
    if lvols:
        lvm.update({'logical_volumes': lvols})
    if pvols:
        lvm.update({'physical_volumes': pvols})
    if vgroups:
        lvm.update({'volume_groups': vgroups})
    if report:
        lvm.update({'report': report})

    return lvm
