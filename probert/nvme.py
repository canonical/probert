# Copyright 2023 Canonical, Ltd.
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

import logging

import pyudev

from probert.utils import udev_get_attributes

log = logging.getLogger('probert.nvme')


async def probe(context=None, **kw):
    if not context:
        context = pyudev.Context()

    nvme_controllers = {}
    for controller in context.list_devices(subsystem='nvme'):
        props = dict(controller.properties)
        props['attrs'] = udev_get_attributes(controller)
        nvme_controllers[controller.sys_name] = props

    return nvme_controllers
