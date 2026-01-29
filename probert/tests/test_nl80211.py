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

import unittest

from probert import nl80211

import pyroute2


class TestNlExceptToRuntimeError(unittest.TestCase):
    def test_decorated_function(self):
        @nl80211.nl_except_to_runtime_err("scanning wifi failed")
        def f():
            # NetlinkDumpInterrupted uses code -1
            raise pyroute2.netlink.exceptions.NetlinkDumpInterrupted()

        with self.assertRaises(RuntimeError, msg="scanning wifi failed -1"):
            f()
