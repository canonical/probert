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

""" This module is a pyroute2-based rewrite of _nl80211module.c (which was a C
implementation using libnl).

NOTE: pyroute2 comes with a "pyroute2.iwutil" module (along with the IW class).
Is is marked experimental but could potentially replace some of the code below.
"""

from typing import Any

import pyroute2
from pyroute2.netlink import NLM_F_ACK, NLM_F_DUMP, NLM_F_REQUEST
from pyroute2.netlink.nl80211 import (NL80211_BSS_STATUS_ASSOCIATED,
                                      NL80211_BSS_STATUS_AUTHENTICATED,
                                      NL80211_BSS_STATUS_IBSS_JOINED,
                                      NL80211_NAMES, nl80211cmd)


def nl_except_to_runtime_err(txt: str):
    """The old nl80211 implementation written in C raised RuntimeError
    exceptions. Pyroute2, on the other hand, raises pyroute2 exceptions (which
    do not inherit from RuntimeError). Use this decorator on nl80211 function
    that previously raised RuntimeErrors - to get a similar behavior."""
    def decorator(func):
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except pyroute2.netlink.exceptions.NetlinkError as nle:
                raise RuntimeError(f"{txt} -{nle.code}") from nle
        return inner
    return decorator


class Listener:
    def __init__(self, observer) -> None:
        self.observer = observer
        self.nl80211 = pyroute2.netlink.nl80211.NL80211()

    @nl_except_to_runtime_err("starting listener failed")
    def start(self) -> None:
        self.nl80211.bind()
        # The "scan" multicast group provides notifications for "TRIGGER_SCAN"
        # and "NEW_SCAN_RESULTS".
        self.nl80211.add_membership("scan")
        # The "mlme" multicast group provides notifications for
        # "ASSOCIATE", "AUTHENTICATE", "CONNECT", "DISCONNECT",
        # "DEAUTHENTICATE", ...
        self.nl80211.add_membership("mlme")

        # Request a dump of all WLAN interfaces to get us started.
        # This will produce "NEW_INTERFACE" events.
        msg = nl80211cmd()
        msg["cmd"] = NL80211_NAMES["NL80211_CMD_GET_INTERFACE"]

        responses = self.nl80211.nlm_request(
            msg, msg_type=self.nl80211.prid,
            msg_flags=NLM_F_REQUEST | NLM_F_DUMP
        )

        for response in responses:
            self.event_handler(response)

    def fileno(self) -> int:
        return self.nl80211.fileno()

    def dump_scan_results(
        self, ifindex: int, only_connected: bool
    ) -> list[tuple[bytes, str]]:
        """Return a list of (ssid, status)"""

        msg = nl80211cmd()

        msg["cmd"] = NL80211_NAMES["NL80211_CMD_GET_SCAN"]
        msg["attrs"] = [["NL80211_ATTR_IFINDEX", ifindex]]

        responses = self.nl80211.nlm_request(
            msg, msg_type=self.nl80211.prid,
            msg_flags=NLM_F_REQUEST | NLM_F_DUMP
        )

        ssids: list[tuple[bytes, str]] = []
        for response in responses:
            if (bss := response.get_attr("NL80211_ATTR_BSS")) is None:
                continue

            status = "no status"
            if (bss_status := bss.get_attr("NL80211_BSS_STATUS")) is not None:
                if bss_status == NL80211_BSS_STATUS_ASSOCIATED:
                    status = "Connected"
                elif bss_status == NL80211_BSS_STATUS_AUTHENTICATED:
                    status = "Authenticated"
                elif bss_status == NL80211_BSS_STATUS_IBSS_JOINED:
                    status = "Joined"
            else:
                if only_connected:
                    continue

            if (ssid := bss.get_nested("NL80211_BSS_INFORMATION_ELEMENTS",
                                       "SSID")):
                ssids.append((ssid, status))

        return ssids

    def event_handler(self, event: nl80211cmd) -> None:
        """Invoke the wlan_event function from the observer, optionally
        including a scan result."""
        ifindex: int | None = event.get_attr("NL80211_ATTR_IFINDEX")

        cmd = None
        if "event" in event:
            cmd = event["event"]

        # To behave the same as the old _nl80211module, we set ifindex=-1 when
        # ifindex is not provided. Going forward though, we should probably
        # leave it as None.
        # Also, the old implementation passed cmd="NL80211_CMD_UNKNOWN" when
        # cmd is unknown, so let's treat the value specially.
        arg: dict[str, Any] = {
            "cmd": (
                cmd.removeprefix("NL80211_CMD_")
                if cmd is not None
                else "NL80211_CMD_UNKNOWN"
            ),
            "ifindex": ifindex if ifindex is not None else -1,
        }

        if ifindex is not None:
            if cmd == "NL80211_CMD_NEW_SCAN_RESULTS":
                arg["ssids"] = self.dump_scan_results(
                    ifindex=ifindex, only_connected=False
                )
            elif cmd in ("NL80211_CMD_ASSOCIATE", "NL80211_CMD_NEW_INTERFACE"):
                arg["ssids"] = self.dump_scan_results(
                    ifindex=ifindex, only_connected=True
                )

        self.observer.wlan_event(arg)

    def data_ready(self) -> None:
        for event in self.nl80211.get():
            self.event_handler(event)

    @nl_except_to_runtime_err("triggering scan failed")
    def trigger_scan(self, ifindex: int) -> None:
        msg = nl80211cmd()

        msg["cmd"] = NL80211_NAMES["NL80211_CMD_TRIGGER_SCAN"]
        msg["attrs"] = [["NL80211_ATTR_IFINDEX", ifindex]]

        self.nl80211.nlm_request(
            msg, msg_type=self.nl80211.prid,
            msg_flags=NLM_F_REQUEST | NLM_F_ACK
        )
