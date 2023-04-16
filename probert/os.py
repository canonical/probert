# Copyright 2011-2021 Canonical, Ltd.
# Copyright 2014 Chris Bainbridge
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

import functools
import logging
import re
import shutil
import subprocess

log = logging.getLogger('probert.os')


def _parse_osprober(lines):
    ret = {}
    for line in lines:
        chunks = line.split(':')
        if len(chunks) != 4:
            log.debug(f'malformed osprober line: {line}')
            continue
        (path, _long, label, _type) = chunks

        # LP: #1265192, fix os-prober Windows EFI path
        match = re.match(r'([/\w\d]+)(@(.+))?', path)
        if not match:
            log.debug(f'malformed osprober line: {line}')
            continue
        partition, _, subpath = match.groups()

        version = None
        if label.startswith('Ubuntu'):
            versions = [v for v in re.findall('[0-9.]+', _long) if v]
            if versions:
                version = versions[0]

            # Get rid of the superfluous (development version) (11.04)
            _long = re.sub(r'\s*\(.*\).*', '', _long)
        else:
            _long = _long.replace(' (loader)', '')

        vals = dict(long=_long, label=label, type=_type)
        if version:
            vals['version'] = version
        if subpath:
            vals['subpath'] = subpath
        ret[partition] = vals
    return ret


@functools.lru_cache(maxsize=1)
def _run_os_prober():
    for cmd in 'subiquity.os-prober', 'os-prober':
        if shutil.which(cmd):
            break
    else:
        log.error('failed to locate os-prober')
        return None
    try:
        result = subprocess.run([cmd], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True, check=True)
        return result.stdout or ''
    except subprocess.CalledProcessError as cpe:
        log.exception('Failed to probe OSes\n%s', cpe.stderr or '')
        return None


async def probe(context=None, **kw):
    """Capture detected OSes. Indexed by partition as decided by os-prober."""
    output = _run_os_prober()
    if not output:
        return {}
    return _parse_osprober(output.splitlines())
