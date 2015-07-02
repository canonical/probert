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
import logging

from probert.utils import dict_merge, udev_get_attribute

log = logging.getLogger('probert.network')


class NetworkInfo():
    ''' properties:
        .type = eth
        .name = eth7
        .vendor = Innotec
        .model = SuperSonicEtherRocket
        .driver = sser
        .devpath = /devices
        .hwaddr = aa:bb:cc:dd:ee:ff
        .addr = 10.2.7.2
        .netmask = 255.255.255.0
        .broadcast = 10.2.7.255
        .addr6 =
        .is_virtual =
        .raw = {raw dictionary}
    '''
    def __init__(self, probe_data):
        [self.name] = probe_data
        self.raw = probe_data.get(self.name)

        self.hwinfo = self.raw['hardware']
        self.hwaddr = self.hwinfo['attrs']['address']
        self.ip = self.raw['ip']
        self.type = self.raw['type']

        # autoset ip related attributes
        for i in self.ip.keys():
            if self.ip[i] is None:
                setattr(self, i, "Unknown")
            else:
                setattr(self, i, self.ip[i])

    def _get_hwvalues(self, keys, missing='Unknown value'):
        for key in keys:
            try:
                return self.hwinfo[key]
            except KeyError:
                log.debug('Failed to get key '
                          '{} from interface {}'.format(key, self.name))
                pass

        return missing

    @property
    def vendor(self):
        keys = [
            'ID_VENDOR_FROM_DATABASE',
            'ID_VENDOR',
            'ID_VENDOR_ID'
        ]
        return self._get_hwvalues(keys=keys, missing='Unknown Vendor')

    @property
    def model(self):
        keys = [
            'ID_MODEL_FROM_DATABASE',
            'ID_MODEL',
            'ID_MODEL_ID'
        ]
        return self._get_hwvalues(keys=keys, missing='Unknown Model')

    @property
    def driver(self):
        keys = [
            'ID_NET_DRIVER',
            'ID_USB_DRIVER',
        ]
        return self._get_hwvalues(keys=keys, missing='Unknown Driver')

    @property
    def devpath(self):
        keys = ['DEVPATH']
        return self._get_hwvalues(keys=keys, missing='Unknown devpath')

    @property
    def is_virtual(self):
        return self.devpath.startswith('/devices/virtual/')


class Network():
    def __init__(self, results={}):
        self.results = results
        self.context = pyudev.Context()

    # these methods extract data from results dictionary
    def get_interfaces(self):
        try:
            return self.results.get('network').keys()
        except (KeyError, AttributeError):
            return []

    def get_ips(self, iface):
        try:
            return self.results.get('network').get(iface).get('ip')
        except (KeyError, AttributeError):
            return []

    def get_hwaddr(self, iface):
        try:
            hwinfo = self.results.get('network').get(iface).get('hardware')
            return hwinfo.get('attrs').get('address')
        except (KeyError, AttributeError):
            return "00:00:00:00:00:00"

    def get_iface_type(self, iface):
        try:
            return self.results.get('network').get(iface).get('type')
        except (KeyError, AttributeError):
            return None

    # the methods below will all probe the host system
    def _get_interfaces(self):
        """ returns list of string interface names """
        return netifaces.interfaces()

    def _get_ips(self, iface):
        """ returns list of dictionary with keys: addr, netmask, broadcast """
        empty = {
            'addr': None,
            'netmask': None,
            'broadcast': None,
        }
        return netifaces.ifaddresses(iface).get(netifaces.AF_INET, [empty])

    def _get_hwaddr(self, iface):
        """ returns dictionary with keys: addr, broadcast """
        [linkinfo] = netifaces.ifaddresses(iface)[netifaces.AF_LINK]
        try:
            return linkinfo.get('addr')
        except AttributeError:
            return None

    def _get_iface_type(self, iface):
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
            results[iface] = {'type': self._get_iface_type(iface)}

            hardware = dict(device)
            hardware.update(
                {'attrs': dict([(key, udev_get_attribute(device, key))
                                for key in device.attributes])})
            results = dict_merge(results, {iface: {'hardware': hardware}})

            [af_inet] = self._get_ips(iface)
            for k in af_inet.keys():
                results = dict_merge(results,
                                     {iface: {'ip': {k: af_inet[k]}}})

        self.results = results
        return results
