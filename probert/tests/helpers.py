# Copyright 2019 Canonical, Ltd.
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

import contextlib
import random
import string
import unittest


@contextlib.contextmanager
def simple_mocked_open(content=None):
    if not content:
        content = ''
    m_open = unittest.mock.mock_open(read_data=content)
    with unittest.mock.patch('builtins.open', m_open, create=True):
        yield m_open


def random_string(length=8):
    """ return a random lowercase string with default length of 8"""
    return ''.join(
        random.choice(string.ascii_lowercase) for _ in range(length))
