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

import socket
import unittest
from unittest import mock

from pyroute2 import IPRoute
from pyroute2.netlink.rtnl.ifinfmsg import IFF_UP

from probert.rtnetlink.link import LinkCache
from probert.rtnetlink.listener import EventResult, Listener
from probert.rtnetlink.route import RouteCache
from probert.rtnetlink.route import build_event_data as route_build_event_data
from probert.tests.rtnetlink.test_link import MyMockLink
from probert.tests.rtnetlink.test_route import MyMockRoute


class TestListener(unittest.TestCase):
    def setUp(self):
        self.listener = Listener(mock.Mock())

    def test_msg_handler_cache_handle_nl_msg__new_not_in_cache(self):
        handler = self.listener.msg_handlers["RTM_NEWLINK"]
        link = MyMockLink()

        self.assertEqual(EventResult.NEW,
                         handler.cache_handle_nl_msg(link))

    def test_msg_handler_cache_handle_nl_msg__new_in_cache_not_updated(self):
        handler = self.listener.msg_handlers["RTM_NEWLINK"]
        link = MyMockLink()
        identifier = LinkCache.UniqueIdentifier.from_nl_msg(link)

        self.listener.link_cache[identifier] = link

        self.assertEqual(EventResult.DISCARD,
                         handler.cache_handle_nl_msg(link))

    def test_msg_handler_cache_handle_nl_msg__new_in_cache_updated(self):
        handler = self.listener.msg_handlers["RTM_NEWLINK"]
        l1 = MyMockLink(index=1, address="aa:aa:aa:aa:aa:aa")
        l2 = MyMockLink(index=1, address="bb:bb:bb:bb:bb:bb")
        identifier = LinkCache.UniqueIdentifier.from_nl_msg(l1)

        self.listener.link_cache[identifier] = l1

        self.assertEqual(EventResult.CHANGE, handler.cache_handle_nl_msg(l2))

    def test_msg_handler_cache_handle_nl_msg__del(self):
        handler = self.listener.msg_handlers["RTM_DELLINK"]
        link = MyMockLink()

        export = link.export()
        export["event"] = "RTM_DELLINK"

        with mock.patch.object(link, "export", return_value=export):
            self.assertEqual(EventResult.DEL,
                             handler.cache_handle_nl_msg(link))

    def test_on_link_change__no_change_state(self):
        with mock.patch.object(self.listener.route_cache, "items") as m_items:
            self.listener.on_link_change(MyMockLink(index=1),
                                         MyMockLink(index=1))

        m_items.assert_not_called()

    def test_on_link_change__change_state(self):
        old_link = MyMockLink(index=41, flags=IFF_UP)
        new_link = MyMockLink(index=41, flags=0x0)

        routes = [
            MyMockRoute(dst="192.168.1.0", dst_len=24,
                        family=socket.AF_INET.value, oif=41),
            MyMockRoute(dst="192.168.2.0", dst_len=24,
                        family=socket.AF_INET.value, oif=42),
            MyMockRoute(dst="aaaa::", dst_len=64,
                        family=socket.AF_INET6.value, oif=41),
        ]
        for route in routes:
            identifier = RouteCache.UniqueIdentifier.from_nl_msg(route)
            self.listener.route_cache[identifier] = route

        self.listener.on_link_change(old_link, new_link)
        self.assertEqual(
            [
                mock.call("DEL", route_build_event_data(routes[0])),
                mock.call("DEL", route_build_event_data(routes[2])),
            ], self.listener.observer.route_change.mock_calls,
        )

    def test_start(self):
        p_bind = mock.patch.object(self.listener.ipr, "bind")
        p_links = mock.patch.object(self.listener.ipr, "get_links",
                                    return_value=["l1", "l2"])
        p_addr = mock.patch.object(self.listener.ipr, "get_addr",
                                   return_value=["a1", "a2"])
        p_routes = mock.patch.object(self.listener.ipr, "get_routes",
                                     return_value=["r1", "r2"])
        p_handle = mock.patch.object(self.listener, "handle_nl_msg")

        with p_bind as m_bind, p_links as m_links, p_addr as m_addr, \
             p_routes as m_routes, p_handle as m_handle:
            self.listener.start()

        m_bind.assert_called_once_with()
        m_links.assert_called_once_with()
        m_addr.assert_called_once_with()
        m_routes.assert_called_once_with()

        self.assertEqual(
                [
                    mock.call("l1", emit_change=False),
                    mock.call("l2", emit_change=False),
                    mock.call("a1", emit_change=False),
                    mock.call("a2", emit_change=False),
                    mock.call("r1", emit_change=False),
                    mock.call("r2", emit_change=False),
                ], m_handle.mock_calls)

    def handle_nl_msg(self, type_: str, result: EventResult, emit_change=True):
        # msg should be a nlmsg, but dict is okay as long as we don't call
        # cache_handle_nl_msg or build_event_data
        msg = {"event": type_}

        msg_handler = self.listener.msg_handlers[type_]

        p_cache_handle = mock.patch.object(msg_handler, "cache_handle_nl_msg")
        p_build = mock.patch.object(msg_handler, "build_event_data")

        with p_cache_handle as m_cache_handle, p_build as m_build:
            m_cache_handle.return_value = result

            self.listener.handle_nl_msg(msg, emit_change=emit_change)

        return msg, msg_handler, m_cache_handle, m_build

    def test_handle_nl_msg__new(self):
        res = self.handle_nl_msg("RTM_NEWLINK", result=EventResult.NEW)
        msg, handler, m_cache_handle, m_build = res

        m_cache_handle.assert_called_once_with(msg)
        m_build.assert_called_once_with(msg)
        handler.observer_callback.assert_called_once_with(
                "NEW", m_build())

    def test_handle_nl_msg__delete(self):
        res = self.handle_nl_msg("RTM_DELLINK", result=EventResult.DEL)
        msg, handler, m_cache_handle, m_build = res

        m_cache_handle.assert_called_once_with(msg)
        m_build.assert_called_once_with(msg)
        handler.observer_callback.assert_called_once_with(
                "DEL", m_build())

    def test_handle_nl_msg__change(self):
        res = self.handle_nl_msg("RTM_NEWLINK", result=EventResult.CHANGE)
        msg, handler, m_cache_handle, m_build = res

        m_cache_handle.assert_called_once_with(msg)
        m_build.assert_called_once_with(msg)
        handler.observer_callback.assert_called_once_with(
                "CHANGE", m_build())

    def test_handle_nl_msg__change_no_emit(self):
        res = self.handle_nl_msg("RTM_NEWLINK", result=EventResult.CHANGE,
                                 emit_change=False)
        msg, handler, m_cache_handle, m_build = res

        m_cache_handle.assert_called_once_with(msg)
        m_build.assert_not_called()
        handler.observer_callback.assert_not_called()

    def test_handle_nl_msg__discard(self):
        res = self.handle_nl_msg("RTM_NEWLINK", result=EventResult.DISCARD)
        msg, handler, m_cache_handle, m_build = res

        m_cache_handle.assert_called_once_with(msg)
        m_build.assert_not_called()
        handler.observer_callback.assert_not_called()

    def test_data_ready(self):
        with mock.patch.object(self.listener, "handle_nl_msg") as m_handle:
            with mock.patch.object(self.listener.ipr, "get",
                                   return_value=["msg1", "msg2", "msg3"]):
                self.listener.data_ready()

        self.assertEqual([
                mock.call("msg1"), mock.call("msg2"), mock.call("msg3")],
                m_handle.mock_calls)

    def test_fileno(self):
        # We need to patch the class, not the instance for some reason.
        with mock.patch.object(IPRoute, "fileno", return_value=42):
            self.assertEqual(42, self.listener.fileno())

    def test_set_link_flags(self):
        with mock.patch.object(self.listener.ipr, "link") as m_link:
            self.listener.set_link_flags(ifindex=13, flags=IFF_UP)

        m_link.assert_called_once_with("set", index=13, flags=IFF_UP,
                                       mask=IFF_UP)

    def test_unset_link_flags(self):
        with mock.patch.object(self.listener.ipr, "link") as m_link:
            self.listener.unset_link_flags(ifindex=13, flags=IFF_UP)

        m_link.assert_called_once_with("set", index=13, flags=0x0, mask=IFF_UP)
