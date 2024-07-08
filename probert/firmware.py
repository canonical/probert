# Copyright 2024 Canonical, Ltd.
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

"""Collect information about the firmware. Unlike network and storage, which
support hotplugging, firmware information should not need to be queried
multiple times."""

import logging
import shutil
from typing import Any

from probert.utils import arun


log = logging.getLogger('probert.firmware')


schema = {
    "$schema": "http://json-schema.org/draft-07/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["bios-vendor", "bios-version", "bios-release-date"],
    "properties": {
        "bios-vendor": {
            "type": ["string", "null"],
        },
        "bios-version": {
            "type": ["string", "null"],
        },
        "bios-release-data": {
            "type": ["string", "null"],
        },
    },
}


class FirmwareProber:
    async def _probe_bios_string(self, string: str) -> str | None:
        dmidecode = shutil.which("dmidecode")
        if dmidecode is None:
            log.debug("could not determine bios %s: dmidecode not found",
                      string)
            return None

        out = await arun([dmidecode, "--string", string])
        if out is None:
            log.warning("could not determine bios %s: dmidecode failure",
                        string)
        else:
            out = out.strip()
        return out

    async def probe(self) -> dict[str, Any]:
        return {
            "bios-vendor": await self._probe_bios_string("bios-vendor"),
            "bios-version": await self._probe_bios_string("bios-version"),
            "bios-release-date":
                await self._probe_bios_string("bios-release-date"),
        }
