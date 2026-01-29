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
import enum
import typing

import pyroute2
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl.ifinfmsg import IFF_UP

import probert.rtnetlink.addr
import probert.rtnetlink.link
import probert.rtnetlink.route
from probert.rtnetlink.cache import Cache, CacheEntry


class EventResult(enum.Enum):
    """Enumerates the different outcomes that an event can produce."""
    NEW = "NEW"          # Send a NEW event to the observer
    CHANGE = "CHANGE"    # Send a CHANGE event to the observer
    DEL = "DEL"          # Send a DEL event to the observer

    DISCARD = "DISCARD"  # Do not send any event to the observer


class Listener:
    @dataclasses.dataclass
    class MsgHandler:
        new: str
        cache: Cache
        observer_callback: typing.Callable[[str, dict[str, typing.Any]], None]
        change_callback: typing.Callable[[CacheEntry, CacheEntry], None] | None
        build_event_data: typing.Callable[[nlmsg], dict[str, typing.Any]]

        def cache_handle_nl_msg(self, msg: nlmsg) -> EventResult:
            identifier = self.cache.UniqueIdentifier.from_nl_msg(msg)
            if msg["event"] == self.new:
                if identifier not in self.cache:
                    self.cache[identifier] = msg
                    return EventResult.NEW

                if self.cache.are_entries_equal(self.cache[identifier], msg):
                    # We still update the cache. Values are not necessarily
                    # meaningful but they are more up to date.
                    self.cache[identifier] = msg
                    return EventResult.DISCARD

                if self.change_callback is not None:
                    self.change_callback(self.cache[identifier], msg)

                self.cache[identifier] = msg
                return EventResult.CHANGE
            else:
                self.cache.pop(identifier, None)
                return EventResult.DEL

    def on_link_change(self, old_link: CacheEntry,
                       new_link: CacheEntry) -> None:
        # When an interface goes down, the kernel does not send RTM_DELROUTE
        # message for all routes involving the interface.
        # We still need to notify the observer that such routes are no longer
        # accessible.
        # See https://github.com/thom311/libnl/issues/340
        if new_link["flags"] & IFF_UP or not old_link["flags"] & IFF_UP:
            return

        ifindex = new_link["index"]

        # Collect the routes to remove first, so we don't invalidate iterators.
        routes_to_del = []
        for route_idx, route in self.route_cache.items():
            if probert.rtnetlink.route.get_ifindex(route) == ifindex:
                routes_to_del.append(route_idx)

        for route_to_del in routes_to_del:
            route = self.route_cache.pop(route_to_del)
            self.observer.route_change(
                    "DEL", probert.rtnetlink.route.build_event_data(route))

    def __init__(self, observer) -> None:
        self.observer = observer

        # By default, the groups (aka. membership groups) is RTMGRP_DEFAULT,
        # which includes neighbours, traffic control, MPLS, rules, etc. We
        # don't want to receive notifications for those.
        groups = (
            pyroute2.netlink.rtnl.RTMGRP_LINK
            | pyroute2.netlink.rtnl.RTMGRP_IPV4_IFADDR
            | pyroute2.netlink.rtnl.RTMGRP_IPV6_IFADDR
            | pyroute2.netlink.rtnl.RTMGRP_IPV4_ROUTE
            | pyroute2.netlink.rtnl.RTMGRP_IPV6_ROUTE
        )

        self.ipr = pyroute2.IPRoute(groups=groups)

        # The caches allow us to discard repetitive NEW events or to emit
        # CHANGE events when appropriate.
        self.link_cache = probert.rtnetlink.link.LinkCache()
        self.addr_cache = probert.rtnetlink.addr.AddrCache()
        self.route_cache = probert.rtnetlink.route.RouteCache()

        self.msg_handlers = {
            "RTM_NEWLINK": self.MsgHandler(
                new="RTM_NEWLINK",
                cache=self.link_cache,
                observer_callback=self.observer.link_change,
                build_event_data=probert.rtnetlink.link.build_event_data,
                change_callback=self.on_link_change,
            ), "RTM_NEWADDR": self.MsgHandler(
                new="RTM_NEWADDR",
                cache=self.addr_cache,
                observer_callback=self.observer.addr_change,
                build_event_data=probert.rtnetlink.addr.build_event_data,
                change_callback=None,
            ), "RTM_NEWROUTE": self.MsgHandler(
                new="RTM_NEWROUTE",
                cache=self.route_cache,
                observer_callback=self.observer.route_change,
                build_event_data=probert.rtnetlink.route.build_event_data,
                change_callback=None,
            ),
        }
        self.msg_handlers["RTM_DELLINK"] = self.msg_handlers["RTM_NEWLINK"]
        self.msg_handlers["RTM_DELADDR"] = self.msg_handlers["RTM_NEWADDR"]
        self.msg_handlers["RTM_DELROUTE"] = self.msg_handlers["RTM_NEWROUTE"]

    def start(self) -> None:
        # By default IPRoute adds membership for RTMGRP_LINK
        self.ipr.bind()

        for msg in self.ipr.get_links():
            self.handle_nl_msg(msg, emit_change=False)
        for msg in self.ipr.get_addr():
            self.handle_nl_msg(msg, emit_change=False)
        for msg in self.ipr.get_routes():
            self.handle_nl_msg(msg, emit_change=False)

    def fileno(self) -> int:
        return self.ipr.fileno()

    def handle_nl_msg(self, msg: nlmsg, *, emit_change=True) -> None:
        handler = self.msg_handlers[msg["event"]]
        result = handler.cache_handle_nl_msg(msg)

        if result == EventResult.DISCARD:
            return

        # Useful when populating the cache the first time.
        if result == EventResult.CHANGE and not emit_change:
            return

        handler.observer_callback(result.value, handler.build_event_data(msg))

    def data_ready(self) -> None:
        for msg in self.ipr.get():
            self.handle_nl_msg(msg)

    def set_link_flags(self, ifindex: int, flags: int) -> None:
        self.ipr.link("set", index=ifindex, flags=flags, mask=flags)

    def unset_link_flags(self, ifindex: int, flags: int) -> None:
        self.ipr.link('set', index=ifindex, flags=0x0, mask=flags)
