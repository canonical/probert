# Copyright 2015 Canonical, Ltd.
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

import re
import subprocess

LSBLK_VERSIONS = ["2.26.2", "2.20.1"]

LSBLK_FIELDS = {
    "2.26.2": [
        "ALIGNMENT",
        "FSTYPE",
        "GROUP",
        "KNAME",
        "LABEL",
        "MODEL",
        "MOUNTPOINT",
        "NAME",
        "OWNER",
        "PARTFLAGS",
        "PARTTYPE",
        "PARTUUID",
        "PKNAME",
        "ROTA",
        "SERIAL",
        "SIZE",
        "STATE",
        "SUBSYSTEMS",
        "TRAN",
        "TYPE",
        "UUID",
        "WWN"
    ],
    "2.20.1": [
        "ALIGNMENT",
        "FSTYPE",
        "GROUP",
        "KNAME",
        "LABEL",
        "MODEL",
        "MOUNTPOINT",
        "NAME",
        "OWNER",
        "ROTA",
        "SIZE",
        "STATE",
        "TYPE",
        "UUID",
    ],
    "default": [
        "ALIGNMENT",
        "FSTYPE",
        "GROUP",
        "KNAME",
        "LABEL",
        "MODEL",
        "MOUNTPOINT",
        "NAME",
        "OWNER",
        "ROTA",
        "SIZE",
        "STATE",
        "TYPE",
        "UUID",
    ],
}

LSBLK_PARAMS = {
    "2.26.2": "-e 1,7 -P -p -b -o",
    "2.20.1": "-e 1,7 -P -b -o",
    "default": "-e 1,7 -P -b -o",
}


def lsblk_version(version):
    v = version.split("-")[0]
    if v in LSBLK_VERSIONS:
        return v
    else:
        return "default"

# regex to recognize the lsblk --pairs output
LSBLK_REGEX = re.compile(r"\b(\w+)\s*=\s*([^=]*)(?=\s+\w+\s*=|$)")


class Storage():
    def __init__(self):
        self.version = "default"
        self.results = {}
        self.command = self._build_command()

    def set_version(self, version):
        self.version = version
        self.results.update({'version': self.version})

    def _build_command(self):
        version_cmd = 'dpkg-query --show -f${Version} util-linux'
        version_string = subprocess.check_output(version_cmd.split(),
                                                 universal_newlines=True)
        self.set_version(lsblk_version(version_string))
        params = LSBLK_PARAMS[self.version]
        fields = LSBLK_FIELDS[self.version]
        cmd = "lsblk {} {}".format(params, ",".join(fields))

        self.results.update({'command': cmd})
        return cmd

    def probe(self):
        cmd_output = subprocess.check_output(self.command.split(),
                                             universal_newlines=True)
        for line in cmd_output.split('\n'):
            d = dict(LSBLK_REGEX.findall(line.replace('"', '')))
            if 'NAME' in d:
                if self.version in ["2.20.1", "default"]:
                    d['NAME'] = '/dev/' + d['NAME']
                    d['KNAME'] = '/dev/' + d['KNAME']
                self.results[d['NAME']] = d

        return self.results
