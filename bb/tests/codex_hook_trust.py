#!/usr/bin/env python3
"""Exact GC hook onboarding for disposable Codex acceptance cities.

Uses native per-handler trust, never the invocation-wide bypass. Only the
reviewed hook sets below are trusted, each exactly as one GC hook generation
writes .codex/hooks.json; any other text keeps Codex's normal review gate and
the launch wrapper refuses it.

Trust digests follow Codex's hook_hash (codex-rs/hooks/src/engine/discovery.rs)
and version_for_toml (codex-rs/config/src/fingerprint.rs): SHA-256 over the
canonical (key-sorted, compact) JSON of the normalized identity
{"event_name": <hook_event_key_label>, "matcher": <matcher>, "hooks": [{"type":
"command", "command": <command>, "timeout": 600, "async": false}]}. Codex ignores
matchers for UserPromptSubmit (events/common.rs matcher_pattern_for_event), so
that identity has no "matcher"; unset optional handler fields (commandWindows,
statusMessage, additionalContextLimit) are absent from the TOML value. The
persisted key (codex-rs/hooks/src/lib.rs hook_key) is "<hooks.json path>:<event>:
<group>:<handler>"; the hash excludes the source path.

SUPPORTED_CODEX_VERSIONS lists each Codex release whose source was read at its
rust-v tag. rust-v0.153.4 and rust-v0.163.0 have the same hook_hash, hook_key,
matcher_pattern_for_event, NormalizedHookIdentity and hook_config.rs
(MatcherGroup, HookHandlerConfig) serialization. version_for_toml changed from a
hand-written recursive key sort (canonical_json) to serde_json's
sort_all_objects, which serializes the same bytes; 0.163.0's
fingerprint_tests.rs pins that with a known digest. hook_trust_digest()
implements the derivation, and the tests check every reviewed digest and
Codex's own fingerprint vector against it, including the GC 1.5.0 digests
originally reviewed in Codex 0.153.4's /hooks UI.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

# Codex releases whose hook trust derivation was read from source at the tag.
SUPPORTED_CODEX_VERSIONS = {
    "codex-cli 0.153.4": "rust-v0.153.4",
    "codex-cli 0.163.0": "rust-v0.163.0",
}
# Released GC cores whose hook text is the gc-1.5.0 set (see live_acceptance.CORE_COMMITS).
RELEASED_HOOK_SET = "gc-1.5.0"
# GC main since 392bd9134 ("Fix managed provider hook gc lookup", #6579) runs
# "${GC_BIN:-gc}" and appends, rather than prepends, the fallback PATH entries.
# The GC integration build 1.6.0-dev.d0835cd45 (integration/bb @ d0835cd45)
# writes exactly this text into acceptance workspaces (captured in a live
# gcbb-fork run on 2026-10-20; see test_codex_hook_trust.py). Its source can also
# rebind managed hooks with --city <dir> and a "startup" SessionStart matcher
# (#3866, #3808); that text is not reviewed, so the wrapper would refuse it.
CURRENT_HOOK_SET = "gc-main-392bd9134"
REVIEWED_HOOK_SETS = {
    RELEASED_HOOK_SET: ('export PATH="$HOME/go/bin:$HOME/.local/bin:$PATH" && ', (
        ("PreCompact", "pre_compact", 0,
         'gc handoff --auto --hook-format codex "context cycle"',
         "bee211b62b8da88e328988459beb14de6916eaa426323994d9a7ea9a25d8e386"),
        ("SessionStart", "session_start", 0,
         "GC_MANAGED_SESSION_HOOK=1 GC_HOOK_EVENT_NAME=SessionStart gc prime --hook --hook-format codex",
         "10ff376f8efe2e535077b7600c0cda5dea8539e872fa2ca1f0e8a5455c50fdf6"),
        ("UserPromptSubmit", "user_prompt_submit", 0,
         "gc hook run --timeout 15s --timeout-exit-code 0 -- nudge drain --inject --hook-format codex",
         "4fa9de4c2dfb3774df70354a095e680c079f451e46074894b0b53b8a7fcd708e"),
        ("UserPromptSubmit", "user_prompt_submit", 1,
         "gc hook run --timeout 15s --timeout-exit-code 0 -- mail check --inject --hook-format codex",
         "e6c6f7c552feb7aaf44febe3d3bbe447407537db3f88ea318606025328b184d3"),
    )),
    CURRENT_HOOK_SET: ('export PATH="$PATH:$HOME/go/bin:$HOME/.local/bin" && ', (
        ("PreCompact", "pre_compact", 0,
         '"${GC_BIN:-gc}" handoff --auto --hook-format codex "context cycle"',
         "838f7472319ef6ea38bb5487c52d14b14f838e20dc2d986382685e658813c27f"),
        ("SessionStart", "session_start", 0,
         'GC_MANAGED_SESSION_HOOK=1 GC_HOOK_EVENT_NAME=SessionStart "${GC_BIN:-gc}" prime --hook --hook-format codex',
         "8f0a1a7bc2783a8b23c56f3a52924b9bf5afb353c87b28b2cad9cb5e0393b4cb"),
        ("UserPromptSubmit", "user_prompt_submit", 0,
         '"${GC_BIN:-gc}" hook run --timeout 15s --timeout-exit-code 0 -- nudge drain --inject --hook-format codex',
         "3260a3ade74575354763aaceda14d130905d521d1fff2c01f2da07de012d2688"),
        ("UserPromptSubmit", "user_prompt_submit", 1,
         '"${GC_BIN:-gc}" hook run --timeout 15s --timeout-exit-code 0 -- mail check --inject --hook-format codex',
         "60a172575a4d09c695edb7efdc4894657be67717972c2d0afa6ba4024056535f"),
    )),
}


def hook_set_for(gc_version, released_versions):
    """Released GC cores write the 1.5.0 text; a declared development build, current main's."""
    return RELEASED_HOOK_SET if gc_version in released_versions else CURRENT_HOOK_SET


def reviewed(hook_set):
    if hook_set not in REVIEWED_HOOK_SETS:
        raise ValueError(f"No reviewed Codex hook set named {hook_set!r}")
    return REVIEWED_HOOK_SETS[hook_set]


def version_for_toml(value):
    """Codex's config fingerprint: SHA-256 of key-sorted compact JSON."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hook_trust_digest(event_key, command):
    """Codex hook_hash for one command handler from GC's hooks.json."""
    identity = {"event_name": event_key,
                "hooks": [{"type": "command", "command": command, "timeout": 600, "async": False}]}
    if event_key != "user_prompt_submit":
        identity["matcher"] = ""
    return version_for_toml(identity)


def expected_hooks(hook_set):
    prefix, hooks = reviewed(hook_set)
    events = {}
    for event, _, _, command, _ in hooks:
        group = events.setdefault(event, [{"matcher": "", "hooks": []}])[0]
        group["hooks"].append({"command": prefix + command, "type": "command"})
    return {"hooks": events}


def verify_gc_hooks(workspace, hook_set):
    directory = Path(workspace) / ".codex"
    source = directory / "hooks.json"
    if directory.is_symlink() or source.is_symlink():
        raise ValueError("Reviewed GC hooks must be regular files in the test workspace")
    value = json.loads(source.read_text())
    if value != expected_hooks(hook_set):
        raise ValueError(f"Generated Codex hooks differ from the four reviewed GC hooks ({hook_set})")
    return value


def trust_config(workspaces, codex_version, hook_set):
    if codex_version not in SUPPORTED_CODEX_VERSIONS:
        raise ValueError("Native hook trust requires a Codex release whose hook hash was reviewed: "
                         + ", ".join(SUPPORTED_CODEX_VERSIONS))
    _, hooks = reviewed(hook_set)
    text = []
    for workspace in workspaces:
        source = Path(workspace).resolve() / ".codex/hooks.json"
        for _, event_key, handler_index, _, digest in hooks:
            key = f"{source}:{event_key}:0:{handler_index}"
            text.append(f'[hooks.state.{json.dumps(key)}]\ntrusted_hash = "sha256:{digest}"\n')
    return "".join(text)


def verify_launch(workspace, codex_home, workspaces, env, hook_set):
    workspace = Path(workspace).resolve()
    if workspace not in {Path(p).resolve() for p in workspaces}:
        raise ValueError("Codex hook onboarding is restricted to its test workspaces")
    if not env.get("CODEX_HOME") or Path(env["CODEX_HOME"]).resolve() != Path(codex_home).resolve():
        raise ValueError("Codex hook onboarding requires its isolated CODEX_HOME")
    verify_gc_hooks(workspace, hook_set)


def write_provider_commands(root, codex_bin, codex_home, workspaces, hook_set):
    """Write the executable GC resolves and its explicit wrapped resume command."""
    reviewed(hook_set)
    wrapper = [sys.executable, str(Path(__file__).resolve()),
               "--codex-bin", str(codex_bin), "--codex-home", str(codex_home), "--hook-set", hook_set]
    for workspace in workspaces:
        wrapper.extend(["--workspace", str(workspace)])
    wrapper.append("--")
    launcher = Path(root) / "codex-verified"
    with launcher.open("x") as stream:
        stream.write('#!/bin/sh\nexec ' + shlex.join(wrapper) + ' "$@"\n')
    launcher.chmod(0o700)
    return (f'command = {json.dumps(str(launcher))}\n'
            f'resume_command = {json.dumps(shlex.quote(str(launcher)) + " resume {{.SessionKey}}")}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--codex-home", required=True)
    parser.add_argument("--workspace", action="append", required=True)
    parser.add_argument("--hook-set", required=True, choices=sorted(REVIEWED_HOOK_SETS))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        verify_launch(Path.cwd(), args.codex_home, args.workspace, os.environ, args.hook_set)
    except (OSError, ValueError) as error:
        print(f"Codex acceptance hook verification failed: {error}", file=sys.stderr)
        return 1
    forwarded = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    # Native trust remains enabled. Only the exact four hashes at the known
    # source paths were seeded; other hooks retain Codex's normal review gate.
    os.execv(args.codex_bin, [args.codex_bin, *forwarded])


if __name__ == "__main__":
    sys.exit(main())
