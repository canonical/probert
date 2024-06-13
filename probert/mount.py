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

import json
import logging
import subprocess

log = logging.getLogger('probert.mount')


def findmnt(data=None):
    if not data:
        cmd = ['findmnt', '--bytes', '--json']
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {}

        data = result.stdout.decode('utf-8')

    mounts = {}
    try:
        mounts = json.loads(data)
    except json.decoder.JSONDecodeError as e:
        log.error('Failed to load findmnt json output:', e)

    return mounts


def probe(context=None):
    """The probert uses the util-linux 'findmnt' command which
       dumps a JSON tree of detailed information about _all_
       mounts in the current linux system.
    """
    return findmnt().get('filesystems', {})
