# Copyright 2021 Canonical, Ltd.
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

import subprocess
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, Mock

from probert.os import probe, _parse_osprober, _run_os_prober


class TestOsProber(IsolatedAsyncioTestCase):
    def tearDown(self):
        _run_os_prober.cache_clear()

    def test_empty(self):
        self.assertEqual({}, _parse_osprober([]))

    def test_windows_efi(self):
        lines = ['/dev/sda1@/efi/Microsoft/Boot/bootmgfw.efi:'
                 + 'Windows Boot Manager:Windows:efi']
        expected = {
            '/dev/sda1': {
                'subpath': '/efi/Microsoft/Boot/bootmgfw.efi',
                'long': 'Windows Boot Manager',
                'label': 'Windows',
                'type': 'efi'
            }
        }

        self.assertEqual(expected, _parse_osprober(lines))

    def test_nosubpath(self):
        lines = ['/dev/sda1:Windows Boot Manager:Windows:efi']
        expected = {
            '/dev/sda1': {
                'long': 'Windows Boot Manager',
                'label': 'Windows',
                'type': 'efi'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    def test_malformed(self):
        lines = ['a:b:c', 'a:b', 'a']
        self.assertEqual({}, _parse_osprober(lines))

    def test_twobuntu(self):
        lines = [
            '/dev/sda3:Ubuntu 21.10 (21.10):Ubuntu:linux',
            '/dev/sda4:Ubuntu 21.10 (21.10):Ubuntu1:linux'
        ]
        expected = {
            '/dev/sda3': {
                'long': 'Ubuntu 21.10',
                'label': 'Ubuntu',
                'type': 'linux',
                'version': '21.10'
            },
            '/dev/sda4': {
                'long': 'Ubuntu 21.10',
                'label': 'Ubuntu1',
                'type': 'linux',
                'version': '21.10'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    def test_weirdness(self):
        lines = ['/dev/sda4#garbage:Ubuntu stuff things:Ubuntu:linux']
        expected = {
            '/dev/sda4': {
                'long': 'Ubuntu stuff things',
                'label': 'Ubuntu',
                'type': 'linux'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    def test_at_no_trailer(self):
        lines = ['/dev/sda4@:Ubuntu stuff things:Ubuntu:linux']
        expected = {
            '/dev/sda4': {
                'long': 'Ubuntu stuff things',
                'label': 'Ubuntu',
                'type': 'linux'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    def test_loader(self):
        lines = ['/dev/sda2:Windows 8 (loader):Windows:chain']
        expected = {
            '/dev/sda2': {
                'long': 'Windows 8',
                'label': 'Windows',
                'type': 'chain'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    def test_winxp(self):
        lines = ['/dev/sda1:Windows XP Professional:Windows:chain']
        expected = {
            '/dev/sda1': {
                'long': 'Windows XP Professional',
                'label': 'Windows',
                'type': 'chain'
            }
        }
        self.assertEqual(expected, _parse_osprober(lines))

    @patch('probert.os.subprocess.run')
    @patch('probert.os.shutil.which', Mock())
    async def test_osx_run(self, run):
        run.return_value.stdout = '/dev/sda4:Mac OS X:MacOSX:macosx\n'
        expected = {
            '/dev/sda4': {
                'long': 'Mac OS X',
                'label': 'MacOSX',
                'type': 'macosx'
            }
        }
        self.assertEqual(expected, await probe())

    @patch('probert.os.subprocess.run')
    @patch('probert.os.shutil.which', Mock())
    async def test_empty_run(self, run):
        run.return_value.stdout = ''
        self.assertEqual({}, await probe())

    @patch('probert.os.subprocess.run')
    @patch('probert.os.shutil.which', Mock())
    async def test_none_run(self, run):
        run.return_value.stdout = None
        self.assertEqual({}, await probe())

    @patch('probert.os.subprocess.run')
    @patch('probert.os.shutil.which', Mock())
    async def test_osprober_fail(self, run):
        run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        self.assertEqual({}, await probe())

    @patch('probert.os.subprocess.run')
    @patch('probert.os.shutil.which', Mock())
    async def test_run_once(self, run):
        run.return_value.stdout = ''
        self.assertEqual({}, await probe())
        self.assertEqual({}, await probe())
        run.assert_called_once()
