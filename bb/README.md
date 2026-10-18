# BB provider for Gas City

Experimental **0.1.0**; not yet a registry release. This pack connects
[BB](https://github.com/get-bb/bb) to a Gas City 1.5+ supervisor through a
generated OpenAPI client pinned in `assets/plugin/contracts/gc/`.

**BB compatibility.** `assets/plugin/package.json` declares BB `>=0.46.0 <0.47`
and plugin SDK `>=0.6.37 <0.7`, the SDK that BB 0.46.0 ships. The plugin is
type-checked and tested against SDK 0.6.37 and also passes against 0.6.49 (BB
0.46.1) and 0.6.52. BB refuses to load the plugin outside these ranges.

The provider also declares `models.experimental_picker` (picker labels and a
"select a project first" prompt). This is an optional enhancement for BB builds
that support it; published BB ignores the key and shows its default model
picker. The catalog is then scoped by the thread's workspace path, which
`gc bb bind --path` maps to a city or rig.

For interactive conversations, configure an agent role that finishes startup
and waits for user messages. GC's default graph-worker role may drain when no
bead work is assigned; BB preserves that configured behavior. The
[conversation role example](./tests/conversation-agent-prompt.md) is a minimal
`prompt.md` for such an agent.

Open **Gas City** in BB’s sidebar. Select a connected host, a standard BB
project, an exact global or rig agent, and its existing workspace. Gas City
retains the agent’s model, prompt, tools, permissions, and runtime configuration.
The launcher requires matching BB/GC directories and never substitutes a
default agent for an unavailable selection.

## Capabilities

| BB concept | Gas City mapping |
| --- | --- |
| Provider | One `gas-city` provider, configured independently on each BB execution host |
| Model choice | Exact configured agent identity: connection + city + qualified agent name |
| Project | Explicit BB project ID → connection + city + rig binding |
| Existing workspace | Longest matching configured checkout/worktree path |
| Thread | One new template-backed GC session, with a durable local ownership receipt |
| Prompt / streamed answer | GC asynchronous submit / structured transcript SSE |
| Interrupt | Stop the session's current turn through GC |
| Release / host disconnect | Detach the BB bridge; retain the GC session |

In BB's native New thread picker, the agent list follows the thread's project
workspace. BB builds that support `models.experimental_picker` label the picker
**Agents** and **Search agents** and list nothing until a project is selected.
Bind a BB city project with `gc bb bind --project <id> --id <id>
--city <city> --path <checkout>` (omit `--rig`) to list that city's global
agents. Add `--rig <rig>` for a rig project to list globals plus that rig's
agents. Project IDs and workspace paths partition BB's model catalog cache,
so a late response for another project cannot replace the current catalog.

Expanded GC configuration is the catalog source, including scale-zero
agent templates. Suspended cities, rigs, and agents are excluded. Qualified
identities distinguish agents across cities, rigs, and connections. Creation
and restore still validate that BB and GC point to the same checkout; catalog
visibility alone does not authorize launching in a different directory.
The separate launcher retains its explicit global discovery mode.

## Prerequisites and topology

- A running Gas City 1.5+ supervisor whose agents report reliable structured
  history and activity. The plugin rejects supervisors older than 1.5 and
  explicit incomplete or failed startup; that minimum version check does not
  qualify every newer release.
- A BB build satisfying the declared ranges above.
- Node.js **22.18+**, npm, and the BB CLI.
- For the initial setup below, the BB server, BB execution host, Gas City, and
  pack checkout are on the same machine and run as the same operator. This
  also makes working-directory checks meaningful.

Use the native transcript roots in `[daemon].observe_paths` and keep native
session identities across resumes.

The adapter runs inside BB's host-side provider infrastructure. There is no
new HTTP service, ACP server, or background process started by importing this
pack. Separate BB hosts need their own GC configuration, filesystem paths,
and journals; a journal is not a portable cross-host session locator.

An ordinary follow-up wakes a sleeping retained session first. This preserves
the native conversation and sends no prompt until readiness and history checks
succeed. GC does not publish readiness on session SSE, so after that one wake
the bridge polls the session (up to 150 seconds) until it is running and
active; transcript streaming and asynchronous delivery results continue to use SSE.

## Stop

BB's interrupt calls GC's `POST /session/{id}/stop`, and only for a conversation
this bridge submitted to. GC does not yet expose a turn identity over HTTP
([gastownhall/gascity#8019](https://github.com/gastownhall/gascity/issues/8019)),
so Stop interrupts the session's current turn. Whether commands the turn
started keep running after Stop is up to GC and the native runtime; the
provider never substitutes a whole-session kill or resubmits the prompt.
Release keeps the session running and is a different operation.

Codex requires persistent consent for project hooks on remote resume, even
when `--dangerously-bypass-hook-trust` was used for a fresh launch. Review and
trust the GC-generated hooks for each city and rig before resuming managed
conversations. Consent applies to exact hook hashes; changed commands require a
new review. The BB provider does not modify hook consent or other native
configuration. Missing consent prevents the session from becoming ready; it
must not trigger a new conversation or a replayed prompt.

## Install

Clone this repository, then import the pack's local path from a Gas City city:

```sh
git clone https://github.com/gastownhall/gascity-packs.git
cd /absolute/path/to/your-city
gc import add --name bb /absolute/path/to/gascity-packs/bb
gc bb install
gc bb connect --id local --url http://127.0.0.1:8372
gc bb status
gc bb agents
```

Use your supervisor's actual URL if it differs. `install` copies the adapter
out of the pack cache, installs locked npm dependencies, builds its helper
CLI, and invokes `bb plugin install path:<installed-directory>`. It forwards
`--yes` only when you explicitly pass it. Importing the pack alone performs
none of these installation steps.

Open the **Gas City** sidebar launcher after binding a standard project below.
Both the launcher and BB's native picker require a mapped standard project;
BB's personal project lists no Gas City agents and cannot host a Gas City
conversation. The launcher lists the mapped city’s global agents alongside
its rig agents.
Select **Full access**: this is the bridge's supported BB permission mode;
the agent's existing Gas City permission policy still applies. GC tmux
approval requests are shown as explicit BB questions offering **Approve once**
and **Deny**. Selecting Full access does not automatically answer them.

To update, pull the checkout and run `gc bb install` again from the city directory.
Each installation is staged under `versions/`, built, and registered with BB
before the `current` symlink changes. Old and failed installations are retained.
A failed registration restores the prior path source without uninstalling its
settings. Existing npm/git registrations are preserved; use BB’s update flow for
those. Configuration and receipts live outside the installation directory.
If an installer was killed, inspect `.install-lock` before retrying; it is never
blindly removed. `gc bb status --json` checks registration, connections, bindings,
and unsettled receipts. It reports configuration readiness, not runtime certification.

## Bind projects and existing workspaces

Use the stable BB project ID, not its display name. For example:

```sh
gc bb bind --project proj_example --id local --city alpha --rig web \
  --path /absolute/path/to/web-checkout \
  --path /absolute/path/to/existing-bb-worktree
gc bb agents --project proj_example --json
gc bb agents --cwd /absolute/path/to/existing-bb-worktree
```

Each path must exist. Multiple `--path` arguments cover existing worktrees;
newly allocated BB worktrees must be bound separately. Rebinding replaces
only that project's mapping on this host. Ambiguous workspace matches and
unmapped standard BB projects produce an error. BB's personal project
(`proj_personal`) remains projectless.

The launcher lists the mapped city’s globals and rig agents together. Select
an agent and verify **Existing workspace**. Use a canonical absolute `work_dir`
in GC configuration; a suggested city/rig path does not establish the effective
execution directory. The provider compares the actual created session directory
before sending input.

**Refresh** bypasses BB’s model catalog cache. Missing hosts, projects and agents
remain unavailable until explicitly selected again. Validation errors can be
corrected and retried. If thread creation has an uncertain outcome, inspect BB’s
thread list before using the explicit retry acknowledgement.

## Checkouts and configuration

Gas City owns the session checkout. The bridge does not silently move a rig
agent into BB's newly created worktree.

- `conversation` (explicit opt-in) allows different directories and posts a visible
  notice in the conversation. BB file and diff views do not automatically
  describe changes made in GC's different checkout.
- `require-match` (default) blocks project prompt submission unless the real BB
  and GC working directories match. Use a matching unmanaged BB environment
  for project work.

Set the policy while configuring a connection:

```sh
gc bb connect --id local --url http://127.0.0.1:8372 \
  --workspace-policy require-match
```

The host-local JSON file defaults to
`${XDG_CONFIG_HOME:-~/.config}/gascity/bb.json`:

```json
{
  "version": 1,
  "workspacePolicy": "require-match",
  "connections": [{ "id": "local", "url": "http://127.0.0.1:8372" }],
  "bindings": [{
    "projectId": "proj_example",
    "connection": "local",
    "city": "alpha",
    "rig": "web",
    "paths": ["/absolute/path/to/web-checkout"]
  }]
}
```

`GC_BB_CONFIG` overrides the config file. `GC_BB_INSTALL_DIR` overrides the
adapter install location (default `${XDG_DATA_HOME:-~/.local/share}/gascity/bb/plugin`).
Receipts live under `${XDG_STATE_HOME:-~/.local/state}/gascity/bb/sessions`.
Configuration and receipts are atomically written with private file modes.

Connections accept loopback HTTP or an authorized HTTPS proxy. An optional
`GC_BB_AUTH_TOKEN` environment variable supplies a bearer token to that proxy;
it is not stored in JSON or exposed in BB model IDs. One token applies to all
configured connections. URL credentials and redirects are rejected.
`X-GC-Request` is sent on writes for GC's request guard; it is not authentication.
Direct hardened deployments requiring GC-specific city grants are outside
this stage; access-denied responses are surfaced to the operator. Remote
proxies do not remove the same-filesystem requirement of this version.

## Conversation lifecycle and recovery

The bridge creates a template-backed GC session with a deterministic alias
derived from the BB thread ID. It waits for the correlated asynchronous
creation result and saves the actual GC session ID. It does not attach to a
pre-existing canonical agent conversation. GC singleton/capacity rules still
apply; choose an agent configuration that permits a new session.

Each text prompt is journaled before posting. A successful submit result means
queued/delivered, not finished. Completion requires new assistant output, a
reliable idle transcript, and no unfinished text, tools, or interactions.
Stream replay is deduplicated by structured message/block identity. The
bridge reports transcript rewrites, degraded history, and unknown interaction
types instead of presenting a successful turn.

When GC supplies a typed terminal provider error, the same delivery and idle
checks settle the BB turn and its receipt as failed. The error is shown in BB,
and an explicit next prompt is allowed after the underlying problem is fixed.
Active retry notices keep the turn open. A GC build that does not publish typed
provider errors can present native Claude API errors as ordinary assistant
messages.

A fresh session can temporarily have only GC's terminal fallback. After checking
the actual workspace, the bridge acknowledges BB's turn promptly and waits up
to 150 seconds for reliable idle structured history before journaling or sending
the first prompt. Startup cancellation or failure sends no prompt. After a
submit, the complete forwarded prompt must appear as a new transcript entry
before output is attributed to that turn. This delivery check also has a bounded
150-second wait. Terminal fallback and startup output cannot satisfy it.
A failed or uncertain submission keeps its receipt for inspection. Existing
conversations require reliable idle history before another prompt is sent.

Completed threads resume the same GC session on the original BB host. An
interrupted stream or uncertain HTTP response can leave remote work running.
The bridge then blocks resubmission/resume until the operator inspects it:

```sh
# Read the complete remote transcript in Gas City first.
gc bb recover --thread <BB-thread-ID> --confirm-reviewed
```

Recovery resolves a lost creation reply through its deterministic alias. For
an unsettled turn it verifies the exact asynchronous submit result, the new
submitted prompt and subsequent settled answer or typed provider failure, and reliable idle history without
pending tools/interactions. Idle history alone does not prove delivery.
It records success or failure from that reviewed outcome; it does not import missing history into BB
or resend the prompt. If the submit reply was lost, supply the original GC
request evidence from inspected events:

```sh
gc bb recover --thread <BB-thread-ID> --confirm-reviewed \
  --request-id <original-GC-request-ID> --event-cursor <original-cursor>
```

Both evidence flags are required together. Older receipts lacking prompt
history evidence remain blocked; retain them and use GC to finish that work.
Each live bridge holds a host-local ownership lease, including between turns.
Release it in BB before recovery. A provably dead process on the same host
allows lock retirement, preserving the original lock. Corrupt, foreign-host,
and otherwise unverifiable locks require inspection. Preserve all receipts
when reinstalling; they prevent duplicate submission.

## Deliberate limits

- The native BB picker and Gas City launcher expose reasoning levels from the
  configured provider's `options_schema` in GC's `/providers/public` response.
  **Agent default** inherits the agent's
  configured effort; an explicit level is sent as `options.effort` at session
  creation. The bridge cannot change effort on an existing session. Keep its
  original selection for subsequent turns, or create a new BB thread to change it.
  GC validates the effective agent options at creation. Its public catalog does
  not reflect agent/workspace `start_command` overrides or every custom provider
  inheritance case, so those configurations may omit supported levels or offer
  levels GC rejects. Use Agent default for custom commands.
- Agent choices are configured, expanded templates. GC's config endpoint
  does not enumerate every dormant named conversation. Generic rig templates
  without a resolved `dir` are skipped with a warning; import roles at rig
  scope so GC expands their identities.
- One active BB turn per session; busy follow-ups fail without clearing the
  active turn or submitting twice. Queue through BB or wait for completion.
  Text input only. Inline attachments, BB
  dynamic tools/skills injection, agent switching, fork, rename, archive,
  manual compaction, and model/tier overrides are not implemented.
- Only the verified GC tmux approval interaction is translated. Other
  interactions require responding in GC and recovering the BB thread.
- GC tools and text appear in BB. Full fidelity usage, specialized tool UI,
  arbitrary named-session attachment, remote checkout adoption, and automatic
  mid-turn reconnect recovery are later stages.
- This version is checked by the fixture, contract and pack tests below. Live
  qualification against published BB 0.46 is still pending, and macOS
  execution is not qualified.

## Development and checks

```sh
cd bb/assets/plugin
npm ci --ignore-scripts
npm run gc:check
npm run typecheck
npm run build
npm test
cd ../../..
GC_TEST_BIN=/absolute/path/to/gc \
  python3 -m unittest discover -s bb/tests -v
```

### Generated supervisor contract

Every runtime HTTP and SSE operation uses the generated OpenAPI SDK in
`assets/plugin/src/generated/gc`. The pinned source is
`assets/plugin/contracts/gc/openapi.json`; its build, source commit and SHA-256
are recorded in `provenance.json`. The snapshot does not certify any GC build
for production or every GC 1.5 deployment. Qualify the exact target supervisor
before relying on it.

From `bb/assets/plugin`:

```sh
npm run gc:generate   # regenerate from the checked-in schema
npm run gc:check      # regenerate into a temporary directory and compare all files
npm run gc:check-live -- http://127.0.0.1:YOUR_PORT
```

Generation uses locked `@hey-api/openapi-ts` 0.99.0 and requires Node 22.18 or
later. Never edit generated files. To update the contract, copy
`internal/api/openapi.json` from the target gastownhall/gascity commit (or
retrieve `/openapi.json` from the target supervisor), review the schema diff,
replace the snapshot, and update its SHA-256, build and source commit in
`provenance.json`. Regenerate, run the checks, then exercise the installed plugin
against that same supervisor. The live check compares the complete schema,
ignoring JSON key order; an additive change also requires review. It uses
`GC_BB_AUTH_TOKEN` when configured and does not print that value.

CI runs the regeneration check and an AST boundary check rejecting handwritten
GC endpoint literals and subprocess imports in session-facing modules. These
are regression guards, not a complete security audit. HTTP authentication,
timeouts and error messages remain in the small client adapter. SSE retains
its existing parser, cancellation and bounded retry policy; the generated SDK
owns routes, parameters and wire types for both transports. BB never uses
native transcripts or tmux as a runtime data source.

The TypeScript tests exercise a GC-shaped HTTP/SSE fixture and BB's
published bridge conformance runner: scoped discovery, exact identities,
async creation, prompt delivery, replay, tool deltas, resume, interrupt,
release, checkout mismatch, lost responses, and explicit approvals.
The Python checks use the **actual GC binary** for pack lint,
resolved configuration, command discovery, and executable entrypoints.
The compatibility workflow (`.github/workflows/bb-provider.yml`) builds the
released GC it pins, runs these checks against it, and builds every plugin
entry with the published BB it pins. It needs no repository secrets. Installer
tests exercise failed builds, registration rollback and retained data.

The layout follows this repository's pack pattern: schema-2 `pack.toml`,
documented `commands/*/run.sh`, a `doctor` check, and adapter code under
`assets/`. No agent definitions or runtime configuration are changed by this
integration.
