# Copyright 2019 Canonical, Ltd.
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

import contextlib
import imp
import importlib
import random
import string
import unittest


def builtin_module_name():
    options = ('builtins', '__builtin__')
    for name in options:
        try:
            imp.find_module(name)
        except ImportError:
            continue
        else:
            print('importing and returning: %s' % name)
            importlib.import_module(name)
            return name


@contextlib.contextmanager
def simple_mocked_open(content=None):
    if not content:
        content = ''
    m_open = unittest.mock.mock_open(read_data=content)
    mod_name = builtin_module_name()
    m_patch = '{}.open'.format(mod_name)
    with unittest.mock.patch(m_patch, m_open, create=True):
        yield m_open


def random_string(length=8):
    """ return a random lowercase string with default length of 8"""
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))
