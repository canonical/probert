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
                             'target_wwnn', 'host_wwpn', 'host_wwpn',
                             'host_adapter'))
MMap = namedtuple("MMap", ('multipath', 'sysfs', 'paths'))
log = logging.getLogger('probert.multipath')


def multipath_show_paths():
    path_format = "%d %z %m %N %n %R %r %a".split()
    cmd = ['multipathd', 'show', 'paths', 'raw', 'format'] + path_format
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    data = result.stdout.decode('utf-8')
    paths = []
    for line in data.splitlines():
        paths.append(MPath(*line.split()))

    return paths


def multipath_show_maps():
    maps_format = "%w %d %N"
    cmd = ['multipathd', 'show', 'maps', 'raw', 'format'] + maps_format
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}

    data = result.stdout.decode('utf-8')
    maps = []
    for line in data.splitlines():
        maps.append(MMap(*line.split()))

    return maps


def probe(context=None):
    results = {}
    maps = multipath_show_maps()
    if maps:
        results.update({'maps': maps})
    paths = multipath_show_paths()
    if paths:
        results.update({'paths': maps})

    return results
