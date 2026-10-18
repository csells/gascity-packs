import copy
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from codex_hook_trust import (CODEX_VERSION, CURRENT_HOOK_SET, RELEASED_HOOK_SET, REVIEWED_HOOK_SETS,
                              expected_hooks, hook_set_for, hook_trust_digest, trust_config,
                              verify_gc_hooks, verify_launch)


class CodexHookTrustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-hook-review-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        (self.workspace / ".codex").mkdir()
        self.hooks = self.workspace / ".codex/hooks.json"
        self.hooks.write_text(json.dumps(expected_hooks(CURRENT_HOOK_SET)))

    def test_every_reviewed_digest_is_the_codex_hook_hash_of_its_exact_command(self):
        # The gc-1.5.0 digests were originally read from Codex's /hooks UI, so
        # matching them also checks the derivation against Codex itself.
        for name, (prefix, hooks) in REVIEWED_HOOK_SETS.items():
            for _, event_key, index, command, digest in hooks:
                with self.subTest(set=name, event=event_key, handler=index):
                    self.assertEqual(hook_trust_digest(event_key, prefix + command), digest)
        self.assertNotEqual(hook_trust_digest("session_start", "gc prime"), hook_trust_digest("session_start", "gc prime "))

    def test_released_cores_select_the_released_text_and_development_builds_current_main(self):
        released = {"1.4.2": "a", "1.5.0": "b"}
        self.assertEqual(hook_set_for("1.5.0", released), RELEASED_HOOK_SET)
        self.assertEqual(hook_set_for("1.6.0-dev-integration.40fa8f780", released), CURRENT_HOOK_SET)

    def test_accepts_only_reviewed_gc_hooks(self):
        self.assertEqual(verify_gc_hooks(self.workspace, CURRENT_HOOK_SET), expected_hooks(CURRENT_HOOK_SET))
        with self.assertRaisesRegex(ValueError, "reviewed"):
            verify_gc_hooks(self.workspace, RELEASED_HOOK_SET)
        with self.assertRaisesRegex(ValueError, "No reviewed"):
            verify_gc_hooks(self.workspace, "whatever-the-binary-wrote")

    def test_rejects_changed_or_extra_hooks(self):
        for mutation in ("command", "matcher", "event", "handler", "metadata"):
            with self.subTest(mutation=mutation):
                payload = copy.deepcopy(expected_hooks(CURRENT_HOOK_SET))
                group = payload["hooks"]["SessionStart"][0]
                if mutation == "command":
                    group["hooks"][0]["command"] += " && unexpected-command"
                elif mutation == "matcher":
                    group["matcher"] = "resume"
                elif mutation == "event":
                    payload["hooks"]["Stop"] = copy.deepcopy([group])
                elif mutation == "handler":
                    group["hooks"].append(copy.deepcopy(group["hooks"][0]))
                else:
                    group["hooks"][0]["async"] = True
                self.hooks.write_text(json.dumps(payload))
                with self.assertRaisesRegex(ValueError, "reviewed"):
                    verify_gc_hooks(self.workspace, CURRENT_HOOK_SET)

    def test_native_trust_is_bound_to_exact_workspace_version_and_hook_set(self):
        for name, digest in ((RELEASED_HOOK_SET, "10ff376f8efe2e535077b7600c0cda5dea8539e872fa2ca1f0e8a5455c50fdf6"),
                             (CURRENT_HOOK_SET, "8f0a1a7bc2783a8b23c56f3a52924b9bf5afb353c87b28b2cad9cb5e0393b4cb")):
            with self.subTest(set=name):
                state = tomllib.loads(trust_config([self.workspace], CODEX_VERSION, name))["hooks"]["state"]
                self.assertEqual(len(state), 4)
                key = f"{self.workspace.resolve()}/.codex/hooks.json:session_start:0:0"
                self.assertEqual(state[key], {"trusted_hash": "sha256:" + digest})
        with self.assertRaisesRegex(ValueError, "0.153.4"):
            trust_config([self.workspace], "codex-cli 0.154.0", CURRENT_HOOK_SET)

    def test_launch_requires_expected_workspace_and_codex_home(self):
        home = self.workspace / "private-codex-home"
        env = {"CODEX_HOME": str(home)}
        verify_launch(self.workspace, home, [self.workspace], env, CURRENT_HOOK_SET)
        with self.assertRaisesRegex(ValueError, "workspaces"):
            verify_launch(self.workspace.parent, home, [self.workspace], env, CURRENT_HOOK_SET)
        for wrong_env in ({}, {"CODEX_HOME": str(self.workspace / "other")}):
            with self.assertRaisesRegex(ValueError, "CODEX_HOME"):
                verify_launch(self.workspace, home, [self.workspace], wrong_env, CURRENT_HOOK_SET)

    def test_rejects_symlinked_source(self):
        other = self.workspace / "other.json"
        other.write_text(json.dumps(expected_hooks(CURRENT_HOOK_SET)))
        self.hooks.unlink()  # this test's disposable fixture only
        self.hooks.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "regular files"):
            verify_gc_hooks(self.workspace, CURRENT_HOOK_SET)


if __name__ == "__main__":
    unittest.main()
