from __future__ import annotations

import unittest

from privacyguard.adapters.presidio import PresidioAdapter, PresidioUnavailable


class PresidioAdapterTests(unittest.TestCase):
    def test_offline_is_explicit_failure(self):
        adapter = PresidioAdapter("http://127.0.0.1:1", timeout=0.2)
        with self.assertRaises(PresidioUnavailable):
            adapter.analyze("alice@example.com")


if __name__ == "__main__":
    unittest.main()
