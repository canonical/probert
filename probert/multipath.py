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
import subprocess

MPath = namedtuple("MPath", ('device', 'serial', 'multipath', 'host_wwnn',
                             'target_wwnn', 'host_wwpn', 'target_wwpn',
                             'host_adapter'))
MMap = namedtuple("MMap", ('multipath', 'sysfs', 'paths'))
MPATH_SHOW = {
    'paths': MPath,
    'maps': MMap,
}

log = logging.getLogger('probert.multipath')


def _extract_mpath_data(cmd, show_verb):
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.error('Failed to run cmd: %s', cmd)
        return []

    mptype = MPATH_SHOW[show_verb]
    data = result.stdout.decode('utf-8')
    result = []
    for line in data.splitlines():
        mp_dict = None
        try:
            field_vals = line.split()
            log.debug('Extracted multipath %s fields: %s',
                      show_verb, *field_vals)
            mp_dict = mptype(*line.split())._asdict()
        except TypeError as e:
            log.debug(
                'Failed to parse multipath %s entry: %s: %s' % (show_verb,
                                                                line, e))
        if mp_dict:
            result.append(mp_dict)

    return result


def multipath_show_paths():
    path_format = "%d %z %m %N %n %R %r %a"
    cmd = ['multipathd', 'show', 'paths', 'raw', 'format', path_format]
    return _extract_mpath_data(cmd, 'paths')


def multipath_show_maps():
    maps_format = "%w %d %N"
    cmd = ['multipathd', 'show', 'maps', 'raw', 'format', maps_format]
    return _extract_mpath_data(cmd, 'maps')


def probe(context=None):
    """Query the multipath daemon for multipath maps and paths.

       This data is useful for determining whether a specific block
       device is part of a multipath and if so which device-mapper (dm)
       blockdevice should be used.

       This probe requires multipath module to be loaded and the multipath
       daemon to be running.
    """
    results = {}
    maps = multipath_show_maps()
    if maps:
        results.update({'maps': maps})
    paths = multipath_show_paths()
    if paths:
        results.update({'paths': paths})

    return results
