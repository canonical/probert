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

from probert.utils import (dict_merge,
                           get_dhclient_d,
                           parse_dhclient_leases_file,
                           parse_networkd_lease_file,
                           parse_etc_network_interfaces,
                           udev_get_attribute)


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
        .ip = { dictionary of addresses }
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
        self.bond = self.raw['bond']
        self.bridge = self.raw['bridge']

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
        self._dhcp_leases = []
        self._etc_network_interfaces = {}

    # these methods extract data from results dictionary
    def get_interfaces(self):
        try:
            return self.results.get('network').keys()
        except (KeyError, AttributeError):
            return []

    def get_routes(self):
        """ returns list of gateways (routes) on the system """
        return netifaces.gateways()

    def get_ips(self, iface):
        try:
            log.debug("get MATT: {}".format(self.results.get('network').get(iface).get('ip')))
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
        ips = { netifaces.AF_INET: netifaces.ifaddresses(iface).get(netifaces.AF_INET, []),
                netifaces.AF_INET6: netifaces.ifaddresses(iface).get(netifaces.AF_INET6, [])
              }
        return ips

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

    def _iface_is_bridge(self, ifname):
        bridge_path = os.path.join('/sys/class/net', ifname, 'bridge')
        return os.path.exists(bridge_path)

    def _iface_is_bridge_port(self, ifname):
        bridge_port = os.path.join('/sys/class/net', ifname, 'brport')
        return os.path.exists(bridge_port)

    def _get_bridge_iface_list(self, ifname):
        if self._iface_is_bridge(ifname):
            bridge_path = os.path.join('/sys/class/net', ifname, 'brif')
            return os.listdir(bridge_path)

        return []

    def _get_bridge_options(self, ifname):
        invalid_attrs = ['flush', 'bridge']  # needs root access, not useful

        options = {}
        if self._iface_is_bridge(ifname):
            bridge_path = os.path.join('/sys/class/net', ifname, 'bridge')
        elif self._iface_is_bridge_port(ifname):
            bridge_path = os.path.join('/sys/class/net', ifname, 'brport')
        else:
            return options

        for bridge_attr_name in [attr for attr in os.listdir(bridge_path)
                                 if attr not in invalid_attrs]:
            bridge_attr_file = os.path.join(bridge_path, bridge_attr_name)
            with open(bridge_attr_file) as bridge_attr:
                options.update({bridge_attr_name: bridge_attr.read().strip()})

        return options

    def _get_bridging(self, ifname):
        ''' return bridge structure for iface
           'bridge': {
              'is_bridge': [True|False],
              'is_port': [True|False],
              'interfaces': [],
              'options': {  # /sys/class/net/brX/bridge/<options key>
                  'sysfs_key': sysfs_value
              },
            }
        '''
        is_bridge = self._iface_is_bridge(ifname)
        is_port = self._iface_is_bridge_port(ifname)
        interfaces = self._get_bridge_iface_list(ifname)
        options = self._get_bridge_options(ifname)
        bridge = {
            'is_bridge': is_bridge,
            'is_port': is_port,
            'interfaces': interfaces,
            'options': options,
        }
        log.debug('bridge info on {}: {}'.format(ifname, bridge))
        return bridge

    def _get_dhcp_leases(self):
        if not self._dhcp_leases:
            lease_d = get_dhclient_d()
            if lease_d:
                lease_files = [file for file in os.listdir(lease_d)
                               if file.endswith('.leases') or
                               file.endswith('.lease')]

            for lf in [os.path.join(lease_d, f) for f in lease_files]:
                with open(lf, 'r') as lease_f:
                    lease_data = lease_f.read()
                    self._dhcp_leases.extend(
                        parse_dhclient_leases_file(lease_data))

            netif_leases_d = '/run/systemd/netif/leases/'
            netif = [file for file in os.listdir(netif_leases_d)]
            for ifindex in netif:
                if_file = os.path.join(netif_leases_d, ifindex)
                netif_lease = None
                with open(if_file, 'r') as lease_f:
                    netif_lease = parse_networkd_lease_file(lease_f.read())
                if netif_lease:
                    netif_lease["interface"] = socket.if_indextoname(int(ifindex))
                    self._dhcp_leases.append(netif_lease)

        return self._dhcp_leases

    def _get_etc_network_interfaces(self):
        if not self._etc_network_interfaces:
            eni = '/etc/network/interfaces'
            with open(eni, 'r') as fp:
                contents = fp.read().strip()
            parse_etc_network_interfaces(self._etc_network_interfaces,
                                         contents,
                                         os.path.dirname(eni))

        return self._etc_network_interfaces

    def _get_dhcp_lease(self, iface):
        ''' Using iface name look on system for indicators that iface might
            have been configured with DHCP

            Heuristics:
                [ -e /var/lib/dhcp/dhclient.<iface>.leases ]
                if grep -q <iface> /var/lib/dhcp/dhclient.leases; then
                   if iface_lease is not expired
                pgrep dhclient

            return dhcp-server-identifier if iface used dhcp, else None
        '''
        # TODO find the most recent lease
        for lease in self._get_dhcp_leases():
            if 'interface' in lease and lease['interface'] == iface:
                return lease

        return None

    def _get_dhcp(self, ifname):
        ''' return dhcp structure for iface
           'dhcp': {
              'active': [True|False],
              'lease': lease_record
            }
        '''
        active = False
        lease = self._get_dhcp_lease(ifname)
        if lease:
            active = True
        dhcp = {
            'active': active,
            'lease': lease,
        }
        log.debug('dhcp info on {}: {}'.format(ifname, dhcp))
        return dhcp

    def _get_ip_source(self, ifname, ip):
        '''Determine the interface's ip source

           'ip': {
               'address': ,
               ...
               'source':  {
                  'method': [dhcp|static],
                  'provider': <dhcp server ip>|<local config>
                  'config': <dhcp_dict> | <eni_config>
               }
           }

           probert inspects the following sources:
              /var/lib/dhcp/*.leases
              /etc/network/interfaces
           As others are added probert will include
           config details from those locations if the
           interface and ip match.
        '''
        source = {}
        if ip:
            dhcp = self._get_dhcp(ifname)
            eni = self._get_etc_network_interfaces()
            manual_source = False
            if dhcp['active']:
                if ('fixed-address' in dhcp['lease'] \
                        and ip['addr'] == dhcp['lease']['fixed-address'] ) \
                        or ('address' in dhcp['lease'] \
                            and ip['addr'] == dhcp['lease']['address']):
                    server_addr = "unknown"
                    if 'options' in dhcp['lease']:
                        server_addr = dhcp['lease']['options']['dhcp-server-identifier']
                    elif 'server_address' in dhcp['lease']:
                        server_addr = dhcp['lease']['server_address']
                    source.update({
                        'method': 'dhcp',
                        'provider':
                        server_addr,
                        'config': dhcp})
                else:
                    manual_source = True
            elif ifname in eni:
                ifcfg = eni[ifname]
                source.update({
                    'method': ifcfg.get('method', 'manual'),
                    'provider': 'local config',
                    'config': ifcfg})
            else:
               manual_source = True

            if manual_source:
                source.update({
                    'method': 'manual',
                    'provider': None,
                    'config': None})

        log.debug('ip source info on {}: {}'.format(ifname, source))
        return source

    def probe(self):
        results = {}
        for device in self.context.list_devices(subsystem='net'):
            iface = device['INTERFACE']
            results[iface] = {
                'type': self._get_iface_type(iface),
                'bond': self._get_bonding(iface),
                'bridge': self._get_bridging(iface),
            }

            hardware = dict(device)
            hardware.update(
                {'attrs': dict([(key, udev_get_attribute(device, key))
                                for key in device.attributes.available_attributes])})
            results = dict_merge(results, {iface: {'hardware': hardware}})

            ip = self._get_ips(iface)
            log.debug('IP res: {}'.format(ip))
            sources = {}
            sources[netifaces.AF_INET] = []
            sources[netifaces.AF_INET6] = []
            for i in range(len(ip[netifaces.AF_INET])):
                sources[netifaces.AF_INET].append(self._get_ip_source(iface, ip[netifaces.AF_INET][i]))
            for i in range(len(ip[netifaces.AF_INET6])):
                sources[netifaces.AF_INET6].append(self._get_ip_source(iface, ip[netifaces.AF_INET6][i]))
            ip.update({'sources': sources})
            results = dict_merge(results, {iface: {'ip': ip}})

        self.results = results
        log.debug('probe results: {}'.format(results))
        return results
