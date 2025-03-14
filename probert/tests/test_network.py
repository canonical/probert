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
from unittest.mock import Mock, patch

from probert.network import UdevObserver


class TestUdevObserver(unittest.TestCase):
    def test_init_no_nl80211(self):
        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "probert" and "_nl80211" in fromlist:
                raise ImportError
            return orig_import(name)

        orig_import = __import__

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(ImportError):
                UdevObserver(with_wlan_listener=True)
            observer = UdevObserver(with_wlan_listener=False)

        self.assertIsNone(observer.wlan_listener)

    def test_init_with_nl80211(self):
        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "probert" and "_nl80211" in fromlist:
                return Mock()
            return orig_import(name)

        orig_import = __import__

        with patch("builtins.__import__", side_effect=fake_import):
            observer = UdevObserver(with_wlan_listener=True)
            self.assertIsNotNone(observer.wlan_listener)

            observer = UdevObserver(with_wlan_listener=False)
            self.assertIsNone(observer.wlan_listener)
