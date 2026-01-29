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

from pyroute2.iproute.ipmock import MockRoute
from pyroute2.netlink.rtnl import rtypes

from probert.rtnetlink.route import RouteCache, build_event_data, get_ifindex
from probert.tests.rtnetlink.common import WithGetAttrMixin


class MyMockRoute(WithGetAttrMixin, MockRoute):
    """Subclass of pyroute2's MockRoute that makes it behave like a nlmsg...
       and works around a bug"""
    def __init__(self, *args, **kwargs):
        # Workaround ambiguity with route type.
        # See https://github.com/svinota/pyroute2/pull/1409
        if "type" in kwargs:
            raise ValueError("please use route_type instead of type")
        if "route_type" in kwargs:
            kwargs["type"] = kwargs["route_type"]
        else:
            kwargs["type"] = rtypes["RTN_UNICAST"]
        super().__init__(*args, **kwargs)


class TestGetIfindex(unittest.TestCase):
    def test_no_multipath(self):
        self.assertEqual(554, get_ifindex(MyMockRoute(oif=554)))

    # TODO Ideally we want a test with multipath involved but
    # MockRoute does not support it so...


class TestRouteBuildEventData(unittest.TestCase):
    def test_route4(self):
        msg = MyMockRoute(dst="192.168.1.0", dst_len=24,
                          family=socket.AF_INET.value, oif=4)

        self.assertEqual({
                "dst": b"192.168.1.0/24",
                "family": socket.AF_INET.value,
                "ifindex": 4,
                "type": rtypes["RTN_UNICAST"],
                "table": 254,
        }, build_event_data(msg))

    def test_default4(self):
        msg = MyMockRoute(dst="0.0.0.0", dst_len=0,
                          family=socket.AF_INET.value, oif=5)

        self.assertEqual({
                "dst": b"default",
                "family": socket.AF_INET.value,
                "ifindex": 5,
                "type": rtypes["RTN_UNICAST"],
                "table": 254,
        }, build_event_data(msg))

    def test_default6(self):
        msg = MyMockRoute(dst="::", dst_len=0,
                          family=socket.AF_INET6.value, oif=5)

        self.assertEqual({
                "dst": b"default",
                "family": socket.AF_INET6.value,
                "ifindex": 5,
                "type": rtypes["RTN_UNICAST"],
                "table": 254,
        }, build_event_data(msg))

    def test_multicast6(self):
        msg = MyMockRoute(dst="ff00::", dst_len=8,
                          family=socket.AF_INET6.value, oif=6,
                          route_type=rtypes["RTN_MULTICAST"], table=255)

        self.assertEqual({
                "dst": b"ff00::/8",
                "family": socket.AF_INET6.value,
                "ifindex": 6,
                "type": rtypes["RTN_MULTICAST"],
                "table": 255,
        }, build_event_data(msg))


class TestRouteCache(unittest.TestCase):
    def test_unique_identifier_from_nl_msg__with_tos(self):
        self.assertEqual(
            RouteCache.UniqueIdentifier(
                family=socket.AF_INET.value, tos=44,
                table=253, dst="1.1.1.0", prio=None),
            RouteCache.UniqueIdentifier.from_nl_msg(MyMockRoute(
                dst="1.1.1.0", dst_len=8, family=socket.AF_INET.value,
                table=253, tos=44))
        )

    def test_unique_identifier_from_nl_msg__with_priority(self):
        self.assertEqual(
            RouteCache.UniqueIdentifier(
                family=socket.AF_INET6.value, tos=0,
                table=254, dst="aaaa::", prio=30),
            RouteCache.UniqueIdentifier.from_nl_msg(MyMockRoute(
                dst="aaaa::", dst_len=72, family=socket.AF_INET6.value,
                priority=30))
        )

    def test_are_entries_equal__equal(self):
        # Identical routes are considered equal
        self.assertTrue(RouteCache.are_entries_equal(
            MyMockRoute(dst="::", dst_len=0,
                        family=socket.AF_INET6.value, oif=5),
            MyMockRoute(dst="::", dst_len=0,
                        family=socket.AF_INET6.value, oif=5),
        ))
        self.assertTrue(RouteCache.are_entries_equal(
            MyMockRoute(dst="192.168.14.0", dst_len=24,
                        family=socket.AF_INET.value, oif=5, table=253),
            MyMockRoute(dst="192.168.14.0", dst_len=24,
                        family=socket.AF_INET.value, oif=5, table=253),
        ))

        # This is arguably a bug in libnl that we replicated but routes with
        # different destlen are considered equal.
        self.assertTrue(RouteCache.are_entries_equal(
            MyMockRoute(dst="192.168.14.0", dst_len=32,
                        family=socket.AF_INET.value),
            MyMockRoute(dst="192.168.14.0", dst_len=24,
                        family=socket.AF_INET.value),
        ))

    def test_are_entries_equal__differ(self):
        # destinations differ (these will be two separate cache entries though)
        self.assertFalse(RouteCache.are_entries_equal(
            MyMockRoute(index=3, family=socket.AF_INET.value, prefixlen=24,
                        dst="10.8.0.0"),
            MyMockRoute(index=3, family=socket.AF_INET.value, prefixlen=24,
                        dst="10.8.1.0"),
        ))

        # priorities differ (these will be two separate cache entries though)
        self.assertFalse(RouteCache.are_entries_equal(
            MyMockRoute(index=3, family=socket.AF_INET.value, prefixlen=24,
                        dst="10.8.0.0", priority=40),
            MyMockRoute(index=3, family=socket.AF_INET.value, prefixlen=24,
                        dst="10.8.0.0", priority=10),
        ))
