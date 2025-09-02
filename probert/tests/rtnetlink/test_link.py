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

from pyroute2.iproute.ipmock import MockLink

from probert.rtnetlink.link import LinkCache, build_event_data
from probert.tests.rtnetlink.common import WithGetAttrMixin


class MyMockLink(WithGetAttrMixin, MockLink):
    """Subclass of pyroute2's MockLink that makes it behave like a nlmsg"""


class TestLinkBuildEventData(unittest.TestCase):
    def test_ethernet(self):
        msg = MyMockLink(index=1, flags=0x0, ifname="eth0")

        self.assertEqual({
                "ifindex": 1,
                "flags": 0x0,
                "arptype": 772,  # hardcoded by MockLink
                "family": socket.AF_UNSPEC.value,  # hardcoded by MockLink
                "is_vlan": False,
                "name": b"eth0",
        }, build_event_data(msg))

    def test_vlan(self):
        msg = MyMockLink(index=334, flags=0x0, ifname="vlan20@eth0",
                         link="eth0", kind="vlan", vlan_id=20)

        self.assertEqual(
            {"ifindex": 334,
             "flags": 0x0,
             "arptype": 772,  # hardcoded by MockLink
             "family": socket.AF_UNSPEC.value,  # hardcoded by MockLink
             "is_vlan": True,
             "vlan_link": "eth0",
             "vlan_id": 20,
             "name": b"vlan20@eth0"}, build_event_data(msg))


class TestLinkCache(unittest.TestCase):
    def test_unique_identifier_from_nl_msg(self):
        self.assertEqual(
                LinkCache.UniqueIdentifier(
                    ifindex=3, family=socket.AF_UNSPEC.value),
                LinkCache.UniqueIdentifier.from_nl_msg(MyMockLink(index=3)))

    def test_are_entries_equal__equal(self):
        # Completely identical links are considered equal
        self.assertTrue(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0"),
            MyMockLink(index=1, flags=0x0, ifname="eth0"),
        ))

        # Links where only stats differ are considered equal
        self.assertTrue(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0",
                       rx_packets=100, tx_packets=100),
            MyMockLink(index=1, flags=0x0, ifname="eth0"),
        ))
        self.assertTrue(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0",
                       rx_packets=1000, tx_packets=1000),
            MyMockLink(index=1, flags=0x0, ifname="eth0",
                       rx_packets=2000, tx_packets=2000),
        ))

    def test_are_entries_equal__differ(self):
        # flags differ
        self.assertFalse(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0"),
            MyMockLink(index=1, flags=0x1, ifname="eth0"),
        ))

        # addresses differ
        self.assertFalse(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0",
                       address="11:11:11:11:11:11"),
            MyMockLink(index=1, flags=0x0, ifname="eth0",
                       address="22:22:22:22:22:22"),
        ))

        # interfaces differ (these will be separate cache entries though)
        self.assertFalse(LinkCache.are_entries_equal(
            MyMockLink(index=1, flags=0x0, ifname="eth0"),
            MyMockLink(index=2, flags=0x0, ifname="eth1"),
        ))
