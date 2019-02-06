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
    return findmnt().get('filesystems', {})
