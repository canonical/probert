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
import operator
import re
import subprocess
from functools import reduce


log = logging.getLogger('probert.zfs')
ZfsListEntry = namedtuple('ZfsListEntry',
                          ('name', 'used', 'avail', 'refer', 'mountpoint'))


def parse_zdb_output(data):
    """ Parse structured zdb output into a dictionary.

    hogshead:
        version: 5000
        name: 'hogshead'
        vdev_tree:
            type: 'root'
            id: 0
            guid: 12392392111803944759
            children[0]:
                type: 'raidz'
                ashift: 12
                children[0]:
                    type: 'disk'
                    id: 0
                    guid: 13921270083288950156
                    path: '/dev/disk/by-id/usb-ST4000VN_000-1H4168-0:0-part1'
                    whole_disk: 1
                    DTL: 140
                    create_txg: 4
                    com.delphix:vdev_zap_leaf: 231
                children[1]:
                    type: 'disk'
                    id: 1
                    guid: 2635788368927674810
                    path: '/dev/disk/by-id/usb-ST4000VN_000-1H4168-0:1-part1'
                    whole_disk: 1
                    DTL: 139
                    create_txg: 4
                    com.delphix:vdev_zap_leaf: 232
    """

    def get_from_dict(datadict, maplist):
        return reduce(operator.getitem, maplist, datadict)

    def set_in_dict(datadict, maplist, value):
        get_from_dict(datadict, maplist[:-1])[maplist[-1]] = value

    def parse_line_key_value(line):
        """ use ': ' token to split line into key, value pairs

        com.delphi:vdev_zap_top: 230
                               ^^
                                `- span() = (24, 26)
        key = 'com.delphi:vdev_zap_top'
        value = '230'
        """
        match = re.search(r': ', line)
        if match:
            tok_start, tok_end = match.span()
            key, value = (line[:tok_start], line[tok_end:])
        else:
            key, value = line.split(':')

        return (key.lstrip(), value.replace("'", ""))

    # for each line in zdb output, calculate the nested level
    # based on indentation. Add key/value pairs for each line
    # and generate a list of keys to calcaulate where in the root
    # dictionary to set the value.
    root = {}
    lvl_tok = 4
    prev_item = []
    for line in data.splitlines():
        current_level = int((len(line) - len(line.lstrip(' '))) / lvl_tok)
        prev_level = len(prev_item) - 1
        key, value = parse_line_key_value(line)
        # TODO: handle children[N] keyname an convert to list
        if current_level == 0:
            root[key] = {}
            prev_item = [(current_level, key)]
        else:
            new_item_path = [item[1]
                             for item in prev_item[0: current_level]] + [key]
            if value:
                set_in_dict(root, new_item_path, value)
            else:
                set_in_dict(root, new_item_path, {})
                # we've dropped down a level, replace prev level key w/new key
                if current_level == prev_level:
                    prev_item.pop()
                prev_item.append((current_level, key))

    return root


def zdb_asdict(data=None):
    """ Convert output from bcache-super-show into a dictionary"""
    if not data:
        cmd = ['zdb']
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # zdb returns non-zero if there are no devices
            return {}

        data = result.stdout.decode('utf-8')

    return parse_zdb_output(data)


def zfs_list_filesystems(raw_output=False):
    cmd = ['zfs', 'list', '-Hp', '-t', 'filesystem']
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []

    data = result.stdout.decode('utf-8')
    if raw_output:
        return data

    # NAME, USED, AVAIL, REFER, MOUNTPOINT
    zfs_entries = []
    for line in data.splitlines():
        (name, used, avail, refer, mpoint) = line.split('\t')
        if mpoint == 'none':
            mpoint = None
        zfs_entries.append(ZfsListEntry(name, used, avail, refer, mpoint))

    return zfs_entries


def zfs_get_properties(zfs_name, raw_output=False):
    if not zfs_name:
        raise ValueError('Invalid zfs_name parameter: "%s"', zfs_name)

    cmd = ['zfs', 'get', 'all', '-Hp', zfs_name]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except subprocess.ProcessExecutionError:
        return []

    data = result.stdout.decode('utf-8')
    if raw_output:
        return data

    # NAME, PROPERTY, VALUE, SOURCE
    zprops = {}
    for line in data.splitlines():
        (name, prop, value, source) = line.split('\t')
        zprops[prop] = {'value': value, 'source': source}

    return {zfs_name: {'properties': zprops}}


def is_zfs_device(device):
    return device.get('ID_FS_TYPE') == 'zfs_member'


def probe(context=None):
    zdb = zdb_asdict()
    zpools = {}
    for zpool, zdb_dump in zdb.items():
        datasets = {}
        zlf = zfs_list_filesystems()
        for zfs_entry in zlf:
            datasets[zfs_entry.name] = zfs_get_properties(zfs_entry.name)
        zpools[zpool] = {'zdb': zdb_dump, 'datasets': datasets}

    return {'zpools': zpools}
