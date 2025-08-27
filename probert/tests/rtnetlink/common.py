# Copyright 2025 Canonical, Ltd.
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

import typing
from collections import UserDict

"""This module provides a helpers to make pyroute2's ipmock classes
behave like nlmsg when it comes to accessing data."""


def get_attr(data: dict[str, typing.Any],
             name: str, default=None) -> typing.Any:
    for attr_name, attr_val in data["attrs"]:
        if attr_name == name:
            if isinstance(attr_val, dict) and "attrs" in attr_val:
                return AttrList(attr_val)
            return attr_val
    return default


class AttrList(UserDict):
    def get_attr(self, *args, **kwargs) -> typing.Any:
        return get_attr(self.data, *args, **kwargs)


class WithGetAttrMixin:
    def __getitem__(self, name: str) -> typing.Any:
        return self.export()[name]

    def get_attr(self, *args, **kwargs) -> typing.Any:
        return get_attr(self.export(), *args, **kwargs)
