import testtools
from probert.storage import Storage


class ProbertTestStorage(testtools.TestCase):
    def setUp(self):
        super(ProbertTestStorage, self).setUp()

    def test_storage_init(self):
        s = Storage()
        self.assertNotEqual(None, s)


    #def test_storage_version(self):
    # mock out call to dpkg-query and supply different version
    # strings and confirm the version value changes with different
    # inputs.

    #def test_storage_command(self):
    # mock out call to dpkg-query and supply different version
    # strings and confirm the command executed changes with different
    # inputs.
