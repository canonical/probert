from copy import deepcopy
import itertools
import os
import re


# from juju-deployer utils.relation_merge
def dict_merge(onto, source):
    target = deepcopy(onto)
    # Support list of relations targets
    if isinstance(onto, list) and isinstance(source, list):
        target.extend(source)
        return target
    for (key, value) in source.items():
        if key in target:
            if isinstance(target[key], dict) and isinstance(value, dict):
                target[key] = dict_merge(target[key], value)
            elif isinstance(target[key], list) and isinstance(value, list):
                target[key] = list(set(target[key] + value))
        else:
            target[key] = value
    return target


# pyudev device
def udev_get_attribute(device, key):
    val = device.attributes.get(key)
    if isinstance(val, bytes):
        return val.decode('utf-8', 'replace')
    return val


# split lists into N lists by predicate
def partitionn2(items, predicate=int, n=2):
    return ((lambda i, tee: (item for pred, item in tee if pred == i))(x, t)
            for x, t in enumerate(itertools.tee(((predicate(item), item)
                                  for item in items), n)))


# unpack generators into key, value pair
# where key is first item (list[0]) and
# value is remainder (list[1:])
def partition_to_pair(input):
    """Unpack a partition into a tuple of (first partition, second partition)

    param: partition iterator from partitionn2
    """
    items = input.split()
    partitions = partitionn2(items=items,
                             predicate=lambda x: items.index(x) != 0,
                             n=2)
    data = [list(p) for p in partitions]
    [key], value = data
    return key, value


def disentagle_data_from_whitespace(data):
    # disentagle the data from whitespace
    return [x.split(';')[0].strip() for x in data.split('\n')
            if len(x)]


def dictify_lease(lease):
    """Transform lease string into dictionary of attributes

    params: lease: string if a dhcp lease structure { to }
    """
    lease_dict = {}
    options = {}
    for line in disentagle_data_from_whitespace(lease):
        key, value = partition_to_pair(line)
        if key == 'option':
            options.update({value[0]: value[1]})
        else:
            value = " ".join(value)
            lease_dict.update({key: value})

    lease_dict.update({'options': options})
    return lease_dict


def parse_dhclient_leases_file(leasedata):
    """Parses dhclient leases file data, returning dictionary of leases

    :param leasesdata: string of lease data read from leases file
    """
    return [dictify_lease(lease) for lease in
            re.findall(r'{([^{}]*)}', leasedata.replace('"', ''))]


def get_dhclient_d():
    # find lease files directory
    supported_dirs = ["/var/lib/dhcp", "/var/lib/dhclient"]
    for d in supported_dirs:
        if os.path.exists(d):
            return d
    return None
