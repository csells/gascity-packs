import unittest

from live_acceptance import GateError, require_development_version


class DevelopmentVersionTests(unittest.TestCase):
    def test_development_build_keeps_its_own_version_stamp(self):
        for version in ("1.6.0-dev-integration.40fa8f780", "1.5.0-dev.002016a8679a", "0.0.0-local"):
            with self.subTest(version=version):
                self.assertEqual(require_development_version(version), version)

    def test_release_or_missing_version_cannot_be_development_evidence(self):
        for version in ("", "1.5.0", "1.4.2"):
            with self.subTest(version=version):
                with self.assertRaises(GateError):
                    require_development_version(version)


if __name__ == "__main__":
    unittest.main()
