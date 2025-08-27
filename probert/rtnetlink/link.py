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

import dataclasses
import typing

from pyroute2.netlink import nlmsg

from probert.rtnetlink.cache import Cache, CacheEntry, CacheEntryComparer


def build_event_data(msg: nlmsg) -> dict[str, typing.Any]:
    link_info = msg.get_attr("IFLA_LINKINFO")
    if link_info:
        is_vlan = link_info.get_attr("IFLA_INFO_KIND") == "vlan"
    else:
        is_vlan = False
    data = {
        "ifindex": msg["index"],
        "flags": msg["flags"],
        "arptype": msg["ifi_type"],
        # This differs from The previous implementation (using libnl) in that
        # we don't override family based on IFLA_LINKINFO -> IFLA_INFO_KIND.
        "family": msg["family"],
        "is_vlan": is_vlan,
        "name": msg.get_attr("IFLA_IFNAME").encode("utf-8"),
    }
    if data["is_vlan"]:
        data["vlan_id"] = link_info.get_attr(
            "IFLA_INFO_DATA").get_attr("IFLA_VLAN_ID")
        data["vlan_link"] = msg.get_attr("IFLA_LINK")
    return data


class LinkCache(Cache):
    @dataclasses.dataclass(frozen=True)
    class UniqueIdentifier:
        """How to uniquely identify a link. This class is used as the key in
        the link cache.
        For more information, see in libnl:
            .oo_id_attrs = LINK_ATTR_IFINDEX | LINK_ATTR_FAMILY
        """
        ifindex: int
        family: int

        @classmethod
        def from_nl_msg(cls, msg: nlmsg) -> "LinkCache.UniqueIdentifier":
            return cls(ifindex=msg["index"], family=msg["family"])

    @staticmethod
    def are_entries_equal(a: CacheEntry, b: CacheEntry) -> bool:
        fields_to_compare = [
            CacheEntryComparer.direct("index"),
            CacheEntryComparer.attr("IFLA_MTU"),
            CacheEntryComparer.attr("IFLA_LINK"),
            CacheEntryComparer.attr("IFLA_LINK_NETNSID"),
            CacheEntryComparer.attr("IFLA_TXQLEN"),
            CacheEntryComparer.attr("IFLA_WEIGHT"),
            CacheEntryComparer.attr("IFLA_MASTER"),
            CacheEntryComparer.direct("family"),
            CacheEntryComparer.attr("IFLA_LINKMODE"),
            CacheEntryComparer.attr("IFLA_QDISC"),
            CacheEntryComparer.attr("IFLA_IFNAME"),
            CacheEntryComparer.attr("IFLA_ADDRESS"),
            CacheEntryComparer.attr("IFLA_BROADCAST"),
            CacheEntryComparer.attr("IFLA_IFALIAS"),
            CacheEntryComparer.attr("IFLA_NUM_VF"),
            CacheEntryComparer.attr("IFLA_PROMISCUITY"),
            CacheEntryComparer.attr("IFLA_NUM_TX_QUEUES"),
            CacheEntryComparer.attr("IFLA_NUM_RX_QUEUES"),
            CacheEntryComparer.direct("flags"),
            # NOTE: For completeness, we should also look at protoinfo and
            # infodata. But these are implementation specific so let's ignore
            # them for now.
        ]
        return CacheEntryComparer.are_equal(a, b, fields=fields_to_compare)
