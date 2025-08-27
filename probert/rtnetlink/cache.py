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

""" This module is part of the pyroute2-based rewrite of _rtnetlinkmodule.c
(which was a C implementation using libnl).
"""

import abc
import collections
import dataclasses
import typing

from pyroute2.netlink import nlmsg

# In the cache, we store the whole netlink message.
# But only the relevant fields are checked for "equality".
CacheEntry: typing.TypeAlias = nlmsg


class CacheEntryComparer:
    """Helpers to compare the content of two entries from the cache."""
    @staticmethod
    def direct(name: str):
        def inner(msg):
            return msg[name]
        return inner

    @staticmethod
    def attr(name: str):
        def inner(msg):
            return msg.get_attr(name)
        return inner

    @staticmethod
    def nested_attr(names: list[str]):
        def inner(msg):
            v = msg
            for name in names:
                v = v.get_attr(name)
                if v is None:
                    return None
            return v
        return inner

    @staticmethod
    def attr_foreach_value(name: str, callback):
        def inner(msg):
            attr = msg.get_attr(name)
            if attr is None:
                return None
            return [callback(item) for item in attr]

        return inner

    @staticmethod
    def are_equal(
            entry_a: CacheEntry, entry_b: CacheEntry, *,
            fields: list[typing.Callable[[CacheEntry], bool]]) -> bool:
        result = True
        for attr_cb in fields:
            if attr_cb(entry_a) != attr_cb(entry_b):
                result = False
        return result


class Cache(collections.UserDict, abc.ABC):
    @dataclasses.dataclass(frozen=True)
    class UniqueIdentifier(abc.ABC):
        @classmethod
        @abc.abstractmethod
        def from_nl_msg(cls, msg: nlmsg) -> "Cache.UniqueIdentifier":
            raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def are_entries_equal(a: CacheEntry, b: CacheEntry) -> bool:
        raise NotImplementedError
