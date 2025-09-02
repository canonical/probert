
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

""" This module is a pyroute2-based rewrite of _rtnetlinkmodule.c (which was a
C implementation using libnl).
"""

import dataclasses
import ipaddress
import typing

from pyroute2.netlink import nlmsg

from probert.rtnetlink.cache import Cache, CacheEntry, CacheEntryComparer


def get_ifindex(msg: nlmsg) -> int | None:
    multipath = msg.get_attr("RTA_MULTIPATH")
    if multipath is not None:
        # A bit cheaty to ignore multipath but ...
        return multipath[0]["oif"]
    else:
        return msg.get_attr("RTA_OIF")
    return None


def build_event_data(msg: nlmsg) -> dict[str, typing.Any]:
    if not msg["dst_len"]:
        dst = "default"
    else:
        addr = msg.get_attr("RTA_DST")
        pfxlen = msg["dst_len"]
        network = ipaddress.ip_network(f"{addr}/{pfxlen}")
        if network.max_prefixlen == pfxlen:
            dst = network.network_address.compressed
        else:
            dst = network.compressed

    ifindex = get_ifindex(msg)

    return {
        "family": msg["family"],
        "type": msg["type"],
        "table": msg["table"],
        "dst": dst.encode("utf-8"),
        "ifindex": ifindex if ifindex is not None else -1,
    }


class RouteCache(Cache):
    @dataclasses.dataclass(frozen=True)
    class UniqueIdentifier:
        """How to uniquely identify a route. This class is used as the key in
        the route cache.
        For more information, see in libnl:
            .oo_id_attrs = (ROUTE_ATTR_FAMILY | ROUTE_ATTR_TOS |
                            ROUTE_ATTR_TABLE | ROUTE_ATTR_DST |
                            ROUTE_ATTR_PRIO),
            .oo_id_attrs_get        = route_id_attrs_get
        """
        family: int
        tos: int
        table: int
        dst: str | None
        prio: int | None    # None for MPLS
        # NOTE: Multiple special routes (e.g. multicast routes) can have the
        # same destination address but a different output interface (i.e.,
        # RTA_OIF). They should probably not be considered the same route (and
        # therefore RTA_OIF should probably be part of the unique identifier).
        # But our previous implementation based on libnl didn't have that
        # today so we're mimicking the behavior.
        # As a result, in the example below, the second route might potentially
        # be discarded since the two routes have the same unique identifier.
        # $ ip -6 route show table 255
        # multicast ff00::/8 dev lxdbr0 proto kernel metric 256 pref medium
        # multicast ff00::/8 dev dummy2 proto kernel metric 256 pref medium

        @classmethod
        def from_nl_msg(cls, msg: nlmsg) -> "RouteCache.UniqueIdentifier":
            return cls(
                family=msg["family"],
                tos=msg["tos"],
                table=msg["table"],
                dst=msg.get_attr("RTA_DST"),
                prio=msg.get_attr("RTA_PRIORITY"),
            )

    @staticmethod
    def are_entries_equal(a: CacheEntry, b: CacheEntry) -> bool:
        def nexthop_multipath(item) -> list[typing.Any]:
            return [
                item["oif"],
                item["hops"],
                item.get_attr("RTA_GATEWAY"),
                item.get_attr("RTA_FLOW"),
                item.get_attr("RTA_NEWDST"),
                item.get_attr("RTA_VIA"),
            ]

        fields_to_compare = [
            CacheEntryComparer.direct("family"),
            CacheEntryComparer.direct("tos"),
            CacheEntryComparer.direct("table"),
            CacheEntryComparer.direct("proto"),
            CacheEntryComparer.direct("scope"),
            CacheEntryComparer.direct("type"),
            CacheEntryComparer.attr("RTA_PRIORITY"),
            CacheEntryComparer.attr("RTA_DST"),
            CacheEntryComparer.attr("RTA_SRC"),
            CacheEntryComparer.attr("RTA_IIF"),
            CacheEntryComparer.attr("RTA_PREFSRC"),
            CacheEntryComparer.attr("RTA_TTL_PROPAGATE"),
            CacheEntryComparer.attr("RTA_METRICS"),
            CacheEntryComparer.direct("flags"),

            # Nexthop without multipath
            CacheEntryComparer.attr("RTA_OIF"),
            CacheEntryComparer.attr("RTA_GATEWAY"),
            CacheEntryComparer.attr("RTA_FLOW"),
            CacheEntryComparer.attr("RTA_NEWDST"),
            CacheEntryComparer.attr("RTA_VIA"),

            # Nexthops with Multipath
            CacheEntryComparer.attr_foreach_value("RTA_MULTIPATH",
                                                  nexthop_multipath)

            # NOTE: For completeness, we should also dig into the RTA_ENCAP
            # nested attribute but this contains implementation specific
            # attributes that are unlikely relevant for us.
        ]
        return CacheEntryComparer.are_equal(a, b, fields=fields_to_compare)
