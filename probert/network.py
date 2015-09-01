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

import fcntl
import os
import netifaces
import pyudev
import socket
import struct
import logging

from probert.utils import dict_merge, udev_get_attribute

log = logging.getLogger('probert.network')

# Soeckt configuration controls (sockios.h)
SIOCGIFFLAGS = 0x8913          # get flags

# Standard interface flags (net/if.h)
IFF_UP = 0x1                   # Interface is up.
IFF_BROADCAST = 0x2            # Broadcast address valid.
IFF_DEBUG = 0x4                # Turn on debugging.
IFF_LOOPBACK = 0x8             # Is a loopback net.
IFF_POINTOPOINT = 0x10         # Interface is point-to-point link.
IFF_NOTRAILERS = 0x20          # Avoid use of trailers.
IFF_RUNNING = 0x40             # Resources allocated.
IFF_NOARP = 0x80               # No address resolution protocol.
IFF_PROMISC = 0x100            # Receive all packets.
IFF_ALLMULTI = 0x200           # Receive all multicast packets.
IFF_MASTER = 0x400             # Master of a load balancer.
IFF_SLAVE = 0x800              # Slave of a load balancer.
IFF_MULTICAST = 0x1000         # Supports multicast.
IFF_PORTSEL = 0x2000           # Can set media type.
IFF_AUTOMEDIA = 0x4000         # Auto media select active.

BONDING_MODES = {
    '0': 'balance-rr',
    '1': 'active-backup',
    '2': 'balance-xor',
    '3': 'broadcast',
    '4': '802.3ad',
    '5': 'balance-tlb',
    '6': 'balance-alb',
}


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

    def get_bond(self, iface):
        try:
            return self.results.get('network').get(iface).get('bonds')
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

    def _get_slave_iface_list(self, ifname):
        try:
            if self._iface_is_master(ifname):
                bond = open('/sys/class/net/%s/bonding/slaves' % ifname).read()
                return bond.split()
        except IOError:
            return []

    def _get_bond_mode(self, ifname):
        try:
            if self._iface_is_master(ifname):
                bond_mode = \
                    open('/sys/class/net/%s/bonding/mode' % ifname).read()
                return bond_mode.split()
        except IOError:
            return None

    def _iface_is_slave(self, ifname):
        return self._is_iface_flags(ifname, IFF_SLAVE)

    def _iface_is_master(self, ifname):
        return self._is_iface_flags(ifname, IFF_MASTER)

    def _is_iface_flags(self, ifname, typ):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        flags, = struct.unpack('H', fcntl.ioctl(s.fileno(), SIOCGIFFLAGS,
                               struct.pack('256s', bytes(ifname[:15],
                                                         'utf=8')))[16:18])
        return (flags & typ) != 0

    def _get_bonding(self, ifname):
        ''' return bond structure for iface
           'bond': {
              'is_master': [True|False]
              'is_slave': [True|False]
              'slaves': []
              'mode': in BONDING_MODES.keys() or BONDING_MODES.values()
            }
        '''
        is_master = self._iface_is_master(ifname)
        is_slave = self._iface_is_slave(ifname)
        slaves = self._get_slave_iface_list(ifname)
        mode = self._get_bond_mode(ifname)
        if mode:
            mode_name = mode[0]
        else:
            mode_name = None
        bond = {
            'is_master': is_master,
            'is_slave': is_slave,
            'slaves': slaves,
            'mode': mode_name
        }
        log.debug('bond info on {}: {}'.format(ifname, bond))
        return bond

    def probe(self):
        results = {}
        for device in self.context.list_devices(subsystem='net'):
            iface = device['INTERFACE']
            results[iface] = {
                'type': self._get_iface_type(iface),
                'bond': self._get_bonding(iface),
            }

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
