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
import ipaddress
import typing

from pyroute2.netlink import nlmsg

from probert.rtnetlink.cache import Cache, CacheEntry, CacheEntryComparer


def build_event_data(msg: nlmsg) -> dict[str, typing.Any]:
    data = {
        "ifindex": msg["index"],
        # msg["flags"] (i.e., ifaddrmsg.ifa_flags) is a 8-bits integer and
        # can only store some of the flags. The IFA_FLAGS attribute is an
        # extension that supports 32-bits flags.
        # See rtnetlink (7)
        "flags": msg.get_attr("IFA_FLAGS", msg["flags"]),
        "family": msg["family"],
        "scope": msg["scope"],
    }

    # * For IPv4, the local address is stored in IFA_LOCAL.
    # * For IPv6, the local address is in IFA_ADDRESS and IFA_LOCAL does
    # not exist.
    # See libnl implementation for details.
    local_addr = msg.get_attr("IFA_LOCAL", msg.get_attr("IFA_ADDRESS"))
    pfxlen = msg["prefixlen"]
    if_local_addr = ipaddress.ip_interface(f"{local_addr}/{pfxlen}")
    if if_local_addr.max_prefixlen == pfxlen:
        local_addr = if_local_addr.ip.compressed
    else:
        local_addr = if_local_addr.compressed
    # For some reason, probert uses decode("latin-1") so let's comply
    # ...
    data["local"] = local_addr.encode("latin-1")

    return data


class AddrCache(Cache):
    @dataclasses.dataclass(frozen=True)
    class UniqueIdentifier:
        """How to uniquely identify an address. This class is used as the key
        in the addr cache.
        For more information, see in libnl:
            .oo_id_attrs_get = addr_id_attrs_get,
            .oo_id_attrs     = (ADDR_ATTR_FAMILY | ADDR_ATTR_IFINDEX |
                                ADDR_ATTR_LOCAL | ADDR_ATTR_PREFIXLEN)
        """
        ifindex: int
        family: int
        prefixlen: int
        # In theory we want: local and optionally peer (depending on family)
        # But let's just include IFA_ADDRESS, IFA_LOCAL
        ifa_local: str | None
        ifa_address: str | None

        @classmethod
        def from_nl_msg(cls, msg: nlmsg) -> "AddrCache.UniqueIdentifier":
            return cls(
                ifindex=msg["index"],
                family=msg["family"],
                prefixlen=msg["prefixlen"],
                ifa_address=msg.get_attr("IFA_ADDRESS"),
                ifa_local=msg.get_attr("IFA_LOCAL"),
            )

    @staticmethod
    def are_entries_equal(a: CacheEntry, b: CacheEntry) -> bool:
        fields_to_compare = [
            CacheEntryComparer.direct("index"),
            CacheEntryComparer.direct("family"),
            CacheEntryComparer.direct("scope"),
            CacheEntryComparer.attr("IFA_LABEL"),
            # local (and peer) addresses.
            CacheEntryComparer.direct("prefixlen"),
            CacheEntryComparer.attr("IFA_ADDRESS"),
            CacheEntryComparer.attr("IFA_LOCAL"),
            CacheEntryComparer.attr("IFA_MULTICAST"),
            CacheEntryComparer.attr("IFA_BROADCAST"),
            CacheEntryComparer.attr("IFA_ANYCAST"),
            CacheEntryComparer.attr("IFA_CACHEINFO"),
            # flags (IFA_FLAGS is a 32-bits extension)
            CacheEntryComparer.direct("flags"),
            CacheEntryComparer.attr("IFA_FLAGS"),
        ]
        return CacheEntryComparer.are_equal(a, b, fields=fields_to_compare)
