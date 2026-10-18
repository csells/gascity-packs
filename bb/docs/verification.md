# Testing the BB provider

This page describes the pack's live acceptance harnesses. Unit, fixture and
installer checks are listed under "Development and checks" in the
[README](../README.md). The runtime versions CI uses are pinned in
`.github/workflows/bb-provider.yml`; a passing run qualifies only those pins.

## CI acceptance

The live jobs in `.github/workflows/bb-provider.yml` run only on manual
workflow dispatch, never on pull requests or pushes, because they need
inference secrets: `MANIFOLD_AUTH_TOKEN` (already used by
`gascity-pack-inference.yml`) or `BB_CLAUDE_API_KEY` for Claude, and
`BB_CODEX_API_KEY` for Codex. Configure those before dispatching.

The `BB end-to-end acceptance` check requires both the build/fixture/CLI job
and real Claude and Codex conversations on the pinned GC release. Each live job
starts a new BB server and host, imports the matching GC core, installs this
checkout, and exercises both a global and a rig agent. It requires:

- A completed first turn that returns markers from both ends of a multiline
  prompt longer than 1 KiB.
- A completed second turn in the same GC session, with a successful BB tool
  event and a new file containing a word remembered from the first turn.
- After suspending only that verified idle agent and waiting for controller
  reconciliation, a third completed turn must recall the first-turn word and
  preserve both GC and provider conversation identities. GC and BB stay running.
- Exact provider, agent, project, host and workspace selection, and correlated
  BB request, acceptance and completion events. An answer alone cannot pass.
- Independent GC transcript and receipt checks proving the full forwarded
  prompt, including BB's context, arrived as a new user message and the
  session is reliably idle. Preserved user markers cannot hide lost context.

Both test agents have an explicit conversational role that finishes startup and
waits for BB user messages. Leaving their role unspecified inherits core's graph
worker, which may correctly drain before receiving a conversational request.
The fixture keeps the core import and real runtime configuration; it does not
override the behavior of agents selected by production users.

Claude CI uses the pinned Claude Code with `BB_CLAUDE_API_KEY` for direct Anthropic
access when configured, otherwise the repository's Manifold credentials and
model aliases. The direct-key route removes the Manifold endpoint, token and
model overrides. The pinned Codex CLI requires the `BB_CODEX_API_KEY` repository
secret, configured after a real Codex API response check. Missing credentials (including on fork PRs), timeouts, failed or
interrupted turns and skipped jobs cannot make the aggregate check pass.
No `pull_request_target` job exposes credentials to fork code.

This is the conversation and agent-resume gate. Approval, denial, repetition,
interrupt and release are covered by the full product gate below; supervisor
restart and recovery remain separate release requirements, and passing this
smoke gate does not waive them. Configure
branch protection to require `BB end-to-end acceptance` if merges must be
enforced by GitHub; defining a workflow alone does not change branch protection.

To run the same live gate locally, use Python 3.11 or later, provide inference
credentials explicitly, and put the released binaries on `PATH` (Node 22, tmux
and the selected runtime):

```sh
python3 -u bb/tests/live_acceptance.py \
  --runtime claude --gc-bin /absolute/path/to/gc \
  --bb-bin /absolute/path/to/bb --bb-app-bin /absolute/path/to/bb-app \
  --report-dir /absolute/path/to/new-report-directory
```

Claude accepts `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or
`CLAUDE_CODE_OAUTH_TOKEN`; custom endpoints/models use the runtime's standard
environment variables. For `--runtime codex`, provide `OPENAI_API_KEY` or set
`BB_ACCEPTANCE_CODEX_AUTH_FILE` to an existing authorized auth JSON file. The
harness copies it into its private, disposable Codex configuration; it never
tests against the original runtime store. All workspaces, cities, BB stores,
ports and tmux sockets are separate from normal work. State remains available
after the harness stops its own services.

Codex also requires trust for hook definitions, separately from workspace
trust. The acceptance harness seeds native trust for exactly four reviewed GC
hooks in its fresh configuration and verifies their definitions before launch.
`bb/tests/codex_hook_trust.py` keeps one reviewed set per GC hook generation
(released 1.5.0, and current main since GC #6579) and documents how each trust
digest is derived from Codex 0.153.4's hook hash; a released GC selects the
released set and a declared development build the current one. Changed or
additional hooks retain normal review requirements. This setup is confined to
the test harness; it does not change the pack's permission policy.

For repeated local checks, keep one isolated GC/BB environment running and call
`bb/tests/live_assertions.py` with its explicit host, project, agent, workspace
and private environment. Add `--existing-thread-id <id>` to exercise fresh turns
in an existing BB conversation. The checker excludes earlier events and still
requires full prompt delivery, correlated completion and the tool artifact.
An uncertain prior submission must be reviewed before another prompt can run.
Add `--exercise-resume` to suspend that verified test agent after its first two
turns and check the third turn's identity and memory. The self-contained CI
harness always enables this check. The checker never restarts either server.

Only `summary.json`, `global/report.json` and `rig/report.json` are CI artifacts.
Raw command captures under `private/` and the separate temporary state directory
can contain credentials and must not be uploaded. The workflow uploads only
those three explicitly named reports.

CI builds the released GC pinned in the workflow and passes its commit with
`--gc-commit`. To validate a GC development build instead, add
`--gc-development-base 1.5.0` and `--gc-commit <full source commit>`. The
binary keeps its own version stamp, for example `1.6.0-dev-integration.40fa8f780`;
only a released version string is refused. The harness then imports the `core`
pin that 1.5.0's `gc init` writes. Reports identify this as development
validation and record the actual version and binary hash; it does not certify a
released binary.

## Full product gate

The conversation gate above is only part of product acceptance. The full gate
drives the released BB frontend, checks GC's native history independently, and
requires every case in `bb/tests/e2e_matrix.py`. A diagnostic subset always
leaves the overall report incomplete. Missing credentials, timeouts, skipped
cases and absent implementations cannot count as passes.

Install the locked browser driver dependencies once:

```sh
npm ci --prefix bb/tests --ignore-scripts
```

For an already prepared, marked scratch installation, reuse its manifest:

```sh
python3 -u bb/tests/full_e2e.py \
  --environment-manifest /absolute/path/to/environment.json \
  --report-dir /absolute/path/to/new-full-report-directory \
  --channel chrome
```

The manifest identifies the isolated BB store, GC home, plugin state, host,
projects, configured agents, credential environment file and exact binaries.
The runner verifies installed pack source, BB/runtime versions, GC commit and
binary hash before executing. It retains all state and private evidence.
Do not construct a manifest pointing at normal user services or data.

For first-time CI preparation, pass `--runtime`, `--gc-bin`, `--gc-commit`,
`--bb-bin` and `--bb-app-bin` instead of a manifest, with the credentials
described above. Development builds also need `--gc-development-base`.
This prepares one isolated installation and retains it for the matrix. Linux
CI installs Playwright's pinned Chromium; local `--channel chrome` uses Chrome.
Only explicit lifecycle cases replace verified test processes. Fresh-install
coverage creates a separate BB store while reusing the same GC controller.

On macOS, `desktop.native` is required. Prepare a copy of the released app with
`desktop_app.py`, attach it with `desktop_attach.mjs`, and set `desktopSpec` in
the manifest to the resulting `desktop.json`. The helper gives the copy its
own profile, cache and bundle identity, verifies the production app archive,
and attaches to the isolated BB endpoint. It never launches the user's app
profile. The desktop journey uses the same completion and native-history
assertions as the browser.

Run both Claude and Codex manifests against the build being reviewed.
Keep `summary.json` and its artifact identities with the validation result;
raw screenshots, traces, event streams, credentials and command captures under
`private/` stay local. The CI full-E2E jobs upload only their scrubbed
summary and require an entirely passing ledger. Branch protection must
separately require the aggregate check.

## Reproduce the browser check

Use an isolated BB/GC installation and model credentials that you control.
Keep its cities, tmux socket, BB data directory, plugin configuration, journals,
provider configuration directories and ports separate from normal work.
The existing workspace must be on the chosen BB host, with a standard project
bound by `gc bb bind`. Install this pack with `gc bb install --yes` from that city.

With Playwright and Chrome installed:

```sh
node bb/tests/live_launcher.mjs \
  --url http://127.0.0.1:<isolated-BB-port> \
  --host <BB-host-ID> --project <BB-project-ID> \
  --model <exact-ID-from-gc-bb-agents> --workspace <existing-workspace>
```

Set `PLAYWRIGHT_MODULE` to an absolute module path if Playwright is installed
outside the project. Without `--prompt`, this checks validation and layout
without creating a model thread. Add `--prompt 'Reply exactly GC_CHECK'` to
create one thread; the command records its URL but does not claim model
completion. Inspect `bb thread log`, `bb thread output`, the GC structured
transcript, and the ownership receipt. Preserve artifacts after failures;
do not resend an uncertain prompt.
