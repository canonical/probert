# Copyright 2015 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import netifaces
import pyudev

from probert.utils import dict_merge, udev_get_attribute


class Network():
    def __init__(self):
        self.results = {}
        self.context = pyudev.Context()

    def get_interfaces(self):
        """ returns list of string interface names """
        return netifaces.interfaces()

    def get_ips(self, iface):
        """ returns list of dictionary with keys: addr, netmask, broadcast """
        empty = {
            'addr': None,
            'netmask': None,
            'broadcast': None,
        }
        return netifaces.ifaddresses(iface).get(netifaces.AF_INET, [empty])

    def get_hwaddr(self, iface):
        """ returns dictionary with keys: addr, broadcast """
        return netifaces.ifaddresses(iface)[netifaces.AF_LINK]

    def get_iface_type(self, iface):
        if len(iface) < 1:
            print('Invalid iface={}'.format(iface))
            return None

        sysfs_path = os.path.join('/sys/class/net', iface)
        if not os.path.exists(sysfs_path):
            print('No sysfs path to {}'.format(sysfs_path))
            return None

        with open(os.path.join(sysfs_path, 'type')) as t:
            type_value = t.read().split('\n')[0]
        if type_value == '1':
            DEV_TYPE = 'eth'
            if os.path.isdir(os.path.join(sysfs_path, 'wireless')) or \
               os.path.islink(os.path.join(sysfs_path, 'phy80211')):
                DEV_TYPE = 'wlan'
            elif os.path.isdir(os.path.join(sysfs_path, 'bridge')):
                DEV_TYPE = 'bridge'
            elif os.path.isfile(os.path.join('/proc/net/vlan', iface)):
                DEV_TYPE = 'vlan'
            elif os.path.isdir(os.path.join(sysfs_path, 'bonding')):
                DEV_TYPE = 'bond'
            elif os.path.isfile(os.path.join(sysfs_path, 'tun_flags')):
                DEV_TYPE = 'tap'
            elif os.path.isdir(
                    os.path.join('/sys/devices/virtual/net', iface)):
                if iface.startswith('dummy'):
                    DEV_TYPE = 'dummy'
        elif type_value == '24':  # firewire ;; IEEE 1394 - RFC 2734
            DEV_TYPE = 'eth'
        elif type_value == '32':  # InfiniBand
            if os.path.isdir(os.path.join(sysfs_path, 'bonding')):
                DEV_TYPE = 'bond'
            elif os.path.isdir(os.path.join(sysfs_path, 'create_child')):
                DEV_TYPE = 'ib'
            else:
                DEV_TYPE = 'ibchild'
        elif type_value == '512':
            DEV_TYPE = 'ppp'
        elif type_value == '768':
            DEV_TYPE = 'ipip'      # IPIP tunnel
        elif type_value == '769':
            DEV_TYPE = 'ip6tnl'   # IP6IP6 tunnel
        elif type_value == '772':
            DEV_TYPE = 'lo'
        elif type_value == '776':
            DEV_TYPE = 'sit'      # sit0 device - IPv6-in-IPv4
        elif type_value == '778':
            DEV_TYPE = 'gre'      # GRE over IP
        elif type_value == '783':
            DEV_TYPE = 'irda'     # Linux-IrDA
        elif type_value == '801':
            DEV_TYPE = 'wlan_aux'
        elif type_value == '65534':
            DEV_TYPE = 'tun'

        if iface.startswith('ippp') or iface.startswith('isdn'):
            DEV_TYPE = 'isdn'
        elif iface.startswith('mip6mnha'):
            DEV_TYPE = 'mip6mnha'

        if len(DEV_TYPE) == 0:
            print('Failed to determine interface type for {}'.format(iface))
            return None

        return DEV_TYPE

    def probe(self):
        results = {}
        for device in self.context.list_devices(subsystem='net'):
            iface = device['INTERFACE']
            results[iface] = {'type': self.get_iface_type(iface)}

            hardware = dict(device)
            hardware.update(
                {'attrs': dict([(key, udev_get_attribute(device, key))
                                for key in device.attributes])})
            results = dict_merge(results, {iface: {'hardware': hardware}})

            [af_inet] = self.get_ips(iface)
            for k in af_inet.keys():
                results = dict_merge(results,
                                     {iface: {'ip': {k: af_inet[k]}}})

        return results
