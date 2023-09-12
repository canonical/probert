import shutil  # noqa: F401
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch


class ProbertTestCase(IsolatedAsyncioTestCase):
    def setUp(self):
        which = patch("shutil.which")
        self.m_which = which.start()
        self.m_which.return_value = '/bin/false'
        self.addCleanup(which.stop)
