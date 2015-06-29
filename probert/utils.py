from copy import deepcopy


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
