import os
import unittest
from unittest import mock

import catalog


class SeedSwitchTests(unittest.TestCase):
    def test_default_is_on(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CATALOG_SEED', None)
            self.assertTrue(catalog.seed_enabled())

    def test_off_values(self):
        for value in ('0', 'false', 'No', 'OFF', ' 0 '):
            with mock.patch.dict(os.environ, {'CATALOG_SEED': value}):
                self.assertFalse(catalog.seed_enabled(), value)

    def test_other_values_keep_it_on(self):
        for value in ('1', 'true', 'yes', ''):
            with mock.patch.dict(os.environ, {'CATALOG_SEED': value}):
                self.assertTrue(catalog.seed_enabled(), value)


if __name__ == '__main__':
    unittest.main()
