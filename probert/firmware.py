# Copyright 2024 Canonical, Ltd.
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
    "required": ["bios-vendor"],
    "properties": {
        "bios-vendor": {
            "type": ["string", "null"],
        },
    },
}


class FirmwareProber:
    async def probe_bios_vendor(self) -> str | None:
        dmidecode = shutil.which("dmidecode")
        if dmidecode is None:
            log.debug("could not determine bios vendor: dmidecode not found")
            return None

        out = await arun([dmidecode, "--string", "bios-vendor"])
        if out is None:
            log.warning("could not determine bios vendor: dmidecode failure")
        else:
            out = out.strip()
        return out

    async def probe(self) -> dict[str, Any]:
        return {"bios-vendor": await self.probe_bios_vendor()}
