import copy
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from codex_hook_trust import (SUPPORTED_CODEX_VERSIONS, CURRENT_HOOK_SET, RELEASED_HOOK_SET, REVIEWED_HOOK_SETS,
                              expected_hooks, hook_set_for, hook_trust_digest, trust_config, version_for_toml,
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
                for version in SUPPORTED_CODEX_VERSIONS:
                    state = tomllib.loads(trust_config([self.workspace], version, name))["hooks"]["state"]
                    self.assertEqual(len(state), 4)
                    key = f"{self.workspace.resolve()}/.codex/hooks.json:session_start:0:0"
                    self.assertEqual(state[key], {"trusted_hash": "sha256:" + digest})
        for unreviewed in ("codex-cli 0.154.0", "codex-cli 0.163.1", "codex-cli 0.163.0-alpha.1", "0.163.0"):
            with self.subTest(version=unreviewed), self.assertRaisesRegex(ValueError, "0.153.4, codex-cli 0.163.0"):
                trust_config([self.workspace], unreviewed, CURRENT_HOOK_SET)

    def test_supported_codex_versions_name_their_source_tags(self):
        self.assertEqual(SUPPORTED_CODEX_VERSIONS, {"codex-cli 0.153.4": "rust-v0.153.4",
                                                    "codex-cli 0.163.0": "rust-v0.163.0"})

    def test_fingerprint_matches_codex_0_163_0_own_test_vector(self):
        # codex-rs/config/src/fingerprint_tests.rs at rust-v0.163.0: the same
        # value with reordered nested keys must keep this exact digest. It pins
        # 0.163.0's sort_all_objects serialization to the canonical JSON used here.
        for value in ({"rows": [{"z": 2, "a": 1}, {"z": 4, "a": 3}], "nested": {"z": "text", "a": True}},
                      {"nested": {"a": True, "z": "text"}, "rows": [{"a": 1, "z": 2}, {"a": 3, "z": 4}]}):
            self.assertEqual(version_for_toml(value), "a5e4c8fbdbc75d185b0f2b5291bfb2de10e8c523d6c89248876fd78a97c83176")

    def test_gc_integration_build_writes_the_current_reviewed_set(self):
        # .codex/hooks.json exactly as GC 1.6.0-dev.d0835cd45 wrote it into a
        # live acceptance workspace in gcbb-fork (2026-10-20).
        written = {"hooks": {
            "PreCompact": [{"hooks": [{"command": 'export PATH="$PATH:$HOME/go/bin:$HOME/.local/bin" && "${GC_BIN:-gc}" handoff --auto --hook-format codex "context cycle"', "type": "command"}], "matcher": ""}],
            "SessionStart": [{"hooks": [{"command": 'export PATH="$PATH:$HOME/go/bin:$HOME/.local/bin" && GC_MANAGED_SESSION_HOOK=1 GC_HOOK_EVENT_NAME=SessionStart "${GC_BIN:-gc}" prime --hook --hook-format codex', "type": "command"}], "matcher": ""}],
            "UserPromptSubmit": [{"hooks": [
                {"command": 'export PATH="$PATH:$HOME/go/bin:$HOME/.local/bin" && "${GC_BIN:-gc}" hook run --timeout 15s --timeout-exit-code 0 -- nudge drain --inject --hook-format codex', "type": "command"},
                {"command": 'export PATH="$PATH:$HOME/go/bin:$HOME/.local/bin" && "${GC_BIN:-gc}" hook run --timeout 15s --timeout-exit-code 0 -- mail check --inject --hook-format codex', "type": "command"}], "matcher": ""}]}}
        self.hooks.write_text(json.dumps(written))
        self.assertEqual(hook_set_for("1.6.0-dev.d0835cd45", {"1.5.0": "core"}), CURRENT_HOOK_SET)
        self.assertEqual(verify_gc_hooks(self.workspace, CURRENT_HOOK_SET), written)
        # The --city rebinding in the same source is not reviewed and is refused.
        rebound = copy.deepcopy(written)
        rebound["hooks"]["SessionStart"][0]["matcher"] = "startup"
        self.hooks.write_text(json.dumps(rebound))
        with self.assertRaisesRegex(ValueError, "reviewed"):
            verify_gc_hooks(self.workspace, CURRENT_HOOK_SET)

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
