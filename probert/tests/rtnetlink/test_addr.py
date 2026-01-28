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

from pyroute2.iproute.ipmock import MockAddress

from probert.rtnetlink.addr import AddrCache, build_event_data
from probert.tests.rtnetlink.common import WithGetAttrMixin


class MyMockAddr(WithGetAttrMixin, MockAddress):
    """Subclass of pyroute2's MockAddr that makes it behave like a nlmsg"""
    # MockAddress in pyroute2 0.9 has default values for index and address but
    # the version in pyroute2 0.7.11 (noble) does not.
    def __init__(self, index=0, address=None, *args, **kwargs) -> None:
        super().__init__(index, address, *args, **kwargs)


class TestAddrBuildEventData(unittest.TestCase):
    def test_inet(self):
        msg = MyMockAddr(index=1, local="192.168.1.1", address="192.168.1.1",
                         prefixlen=24, family=socket.AF_INET.value)

        self.assertEqual({
                "ifindex": 1,
                "flags": 512,  # hardcoded in MockAddress
                "family": socket.AF_INET.value,
                "scope": 0,  # hardcoded in MockAddress
                "local": b"192.168.1.1/24",
        }, build_event_data(msg))

    def test_inet6(self):
        msg = MyMockAddr(index=1, local=None, address="abcd::10",
                         prefixlen=64, family=socket.AF_INET6.value)

        self.assertEqual({
                "ifindex": 1,
                "flags": 512,  # hardcoded in MockAddress
                "family": socket.AF_INET6.value,
                "scope": 0,  # hardcoded in MockAddress
                "local": b"abcd::10/64",
        }, build_event_data(msg))

    def test_inet_point_to_point(self):
        # There is possible confusion between IFA_ADDRESS and IFA_LOCAL, make
        # sure we use the right value. The other would be the peer address.
        msg = MyMockAddr(index=1, address="192.168.1.2", local="192.168.1.1",
                         prefixlen=31, family=socket.AF_INET6.value)

        self.assertEqual({
                "ifindex": 1,
                "flags": 512,  # hardcoded in MockAddress
                "family": socket.AF_INET6.value,
                "scope": 0,  # hardcoded in MockAddress
                "local": b"192.168.1.1/31",
        }, build_event_data(msg))


class TestAddrCache(unittest.TestCase):
    def test_unique_identifier_from_nl_msg__inet(self):
        self.assertEqual(
                AddrCache.UniqueIdentifier(
                    ifindex=3, family=socket.AF_INET.value, prefixlen=24,
                    ifa_local="192.168.1.1", ifa_address="192.168.1.2"),
                AddrCache.UniqueIdentifier.from_nl_msg(MyMockAddr(
                    index=3, family=socket.AF_INET.value, prefixlen=24,
                    local="192.168.1.1", address="192.168.1.2")),
        )

    def test_unique_identifier_from_nl_msg__inet6(self):
        self.assertEqual(
                AddrCache.UniqueIdentifier(
                    ifindex=4, family=socket.AF_INET6.value, prefixlen=72,
                    ifa_address=None, ifa_local="aaaa::1"),
                AddrCache.UniqueIdentifier.from_nl_msg(MyMockAddr(
                    index=4, family=socket.AF_INET6.value, prefixlen=72,
                    address=None, local="aaaa::1"))
        )

    def test_are_entries_equal__equal(self):
        # Identical addresses are considered equal
        self.assertTrue(AddrCache.are_entries_equal(
            MyMockAddr(index=1, family=socket.AF_INET.value, prefixlen=16,
                       local="10.8.1.1"),
            MyMockAddr(index=1, family=socket.AF_INET.value, prefixlen=16,
                       local="10.8.1.1"),
        ))
        self.assertTrue(AddrCache.are_entries_equal(
            MyMockAddr(index=2, family=socket.AF_INET6.value, prefixlen=127,
                       local=None, address="abcd::1"),
            MyMockAddr(index=2, family=socket.AF_INET6.value, prefixlen=127,
                       local=None, address="abcd::1"),
        ))

    def test_are_entries_equal__differ(self):
        # addresses differ (these will be two separate cache entries though)
        self.assertFalse(AddrCache.are_entries_equal(
            MyMockAddr(index=3, family=socket.AF_INET.value, prefixlen=24,
                       local="10.8.1.1"),
            MyMockAddr(index=3, family=socket.AF_INET.value, prefixlen=24,
                       local="10.8.1.2"),
        ))

        # prefixes differ (these will be two separate cache entries though)
        self.assertFalse(AddrCache.are_entries_equal(
            MyMockAddr(index=3, family=socket.AF_INET6.value, prefixlen=64,
                       address="aaaa::1"),
            MyMockAddr(index=3, family=socket.AF_INET6.value, prefixlen=72,
                       address="aaaa::1"),
        ))

        # ifindexes differ
        self.assertFalse(AddrCache.are_entries_equal(
            MyMockAddr(index=3, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10"),
            MyMockAddr(index=4, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10"),
        ))

        # broadcast addresses differ
        self.assertFalse(AddrCache.are_entries_equal(
            MyMockAddr(index=4, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10", broadcast="192.168.0.255"),
            MyMockAddr(index=4, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10", broadcast="192.168.0.250"),
        ))

        # labels differ
        self.assertFalse(AddrCache.are_entries_equal(
            MyMockAddr(index=5, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10", label="mylabel"),
            MyMockAddr(index=5, family=socket.AF_INET.value, prefixlen=24,
                       local="192.168.0.10"),
        ))
