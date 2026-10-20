import tomllib
import unittest

from live_acceptance import GateError, codex_model_config, require_development_version


class DevelopmentVersionTests(unittest.TestCase):
    def test_development_build_keeps_its_own_version_stamp(self):
        for version in ("1.6.0-dev.d0835cd45", "1.6.0-dev-integration.40fa8f780", "1.5.0-dev.002016a8679a", "0.0.0-local"):
            with self.subTest(version=version):
                self.assertEqual(require_development_version(version), version)

    def test_release_or_missing_version_cannot_be_development_evidence(self):
        for version in ("", "1.5.0", "1.4.2"):
            with self.subTest(version=version):
                with self.assertRaises(GateError):
                    require_development_version(version)


class CodexModelConfigTests(unittest.TestCase):
    def test_default_leaves_codex_model_and_provider_unchanged(self):
        self.assertEqual(codex_model_config(), "")

    def test_model_and_provider_precede_tables_and_reuse_the_isolated_key(self):
        text = codex_model_config("gpt-6-astra", "https://works.gascity.com/manifold-api/v1")
        config = tomllib.loads(text + '[projects."/tmp/w"]\ntrust_level = "trusted"\n')
        self.assertEqual(config["model"], "gpt-6-astra")
        self.assertEqual(config["model_provider"], "acceptance")
        self.assertEqual(config["model_providers"]["acceptance"], {
            "name": "acceptance", "base_url": "https://works.gascity.com/manifold-api/v1",
            "wire_api": "responses", "supports_websockets": False, "requires_openai_auth": True})
        self.assertEqual(tomllib.loads(codex_model_config("gpt-6.1-sol")), {"model": "gpt-6.1-sol"})

    def test_rejects_unsafe_model_names_and_endpoints(self):
        for model in ("", "gpt 6", 'x"\nmodel_provider = "evil', "-m"):
            with self.subTest(model=model), self.assertRaises(GateError):
                codex_model_config(model)
        for url in ("http://example.com/v1", "https://user:pw@example.com/v1", "https://example.com/v1?key=x",
                    "https://example.com/v1#x", "file:///etc/passwd", "example.com"):
            with self.subTest(url=url), self.assertRaises(GateError):
                codex_model_config(None, url)
        self.assertIn("http://127.0.0.1:9/v1", codex_model_config(None, "http://127.0.0.1:9/v1"))


if __name__ == "__main__":
    unittest.main()
