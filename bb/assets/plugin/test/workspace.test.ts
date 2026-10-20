import test from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { GasCityProjectRequiredError, GasCityProvider } from "../src/provider.js";
import { GasCityClient } from "../src/client.js";
import { Journal } from "../src/journal.js";
import { targetId } from "../src/catalog.js";
import { fixture, options, until } from "./fixture.js";

const target = { v: 1 as const, connection: "local", city: "alpha", agent: "gc.mayor" };

test("conversation policy runs a mapped project from BB's separate workspace and resumes the same GC session", async () => {
  const f = await fixture(); f.config.workspacePolicy = "conversation";
  const bbCwd = join(f.cwd, "bb-separate-workspace"), gcCwd = join(f.cwd, "gc-city");
  await mkdir(bbCwd); await mkdir(gcCwd); f.faults.workDir = gcCwd;
  const messages: any[] = [];
  let noticeBeforeSubmit = false;
  const provider = new GasCityProvider({
    send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")),
    client: connection => new GasCityClient(connection, async (input, init) => {
      if (String(input).endsWith("/submit")) noticeBeforeSubmit = messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "item.textClose" && d.text?.includes(gcCwd));
      return fetch(input, init);
    }),
  });
  try {
    const args = { threadId: "separate-workspace", cwd: bbCwd, instructionMode: "append", options: { ...options, model: targetId(target), reasoningLevel: "medium", instructions: `BB workspace: ${bbCwd}`, providerOptions: { projectId: "project-web" } } };
    const started: any = await provider.dispatch("thread/start", { ...args, input: [{ type: "text", text: "hello?" }] });
    await until(() => messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "turn.boundary" && d.status === "completed"));
    const creation = f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions"));
    assert.equal(creation.length, 1);
    assert.deepEqual(creation[0]!.body.options, { effort: "medium" });
    const submissions = f.calls.filter(c => c.path.endsWith("/submit")); assert.equal(submissions.length, 1);
    assert.equal(submissions[0]!.body.message.split("hello?").length - 1, 1);
    assert.ok(submissions[0]!.body.message.endsWith("hello?"));
    assert.ok(submissions[0]!.body.message.includes(gcCwd), "GC receives its actual working directory alongside BB context");
    assert.equal(noticeBeforeSubmit, true, "the workspace notice is visible before GC receives the prompt");
    const notice = messages.flatMap(m => m.params?.deltas ?? []).find(d => d.kind === "item.textClose" && d.text?.includes(gcCwd));
    assert.ok(notice, "the conversation names the GC working directory");
    assert.ok(notice.text.includes(bbCwd));
    assert.match(notice.text, /file and diff views.*not synchronized/i);
    await provider.dispatch("thread/stop", { threadId: args.threadId, providerThreadId: started.providerThreadId, intent: "release", activeTurnId: null });
    const resumed: any = await provider.dispatch("thread/resume", { ...args, providerThreadId: started.providerThreadId });
    assert.equal(resumed.providerThreadId, started.providerThreadId);
    assert.equal(f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions")).length, 1);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

for (const agent of ["gc.mayor", "web/review.reviewer"]) {
  test(`mapped project ${agent} rejects a different GC checkout before sending a prompt`, async () => {
    const f = await fixture(); const otherCheckout = join(f.cwd, "other-checkout");
    await mkdir(otherCheckout); f.faults.workDir = otherCheckout;
    const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
    try {
      await assert.rejects(provider.dispatch("thread/start", { threadId: "mapped-mismatch", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId({ ...target, agent }), providerOptions: { projectId: "project-web" } }, input: [{ type: "text", text: "Do not send" }] }), /Select a matching unmanaged/);
      assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    } finally { await provider.close(); await f.close(); }
  });
}

test("Personal-project and unbound conversations fail fast with a typed error before contacting GC", async () => {
  const f = await fixture();
  const elsewhere = await mkdtemp(join(tmpdir(), "bb-unbound-"));
  const messages: any[] = [];
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const input = [{ type: "text", text: "Do not send" }];
    // bb thread spawn --project proj_personal with a city agent or a rig agent,
    // and a workspace that matches no binding when BB names no project.
    const starts = [
      { threadId: "personal-city", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target), providerOptions: { projectId: "proj_personal" } }, input },
      { threadId: "personal-rig", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId({ ...target, agent: "web/review.reviewer" }), providerOptions: { projectId: "proj_personal" } }, input },
      { threadId: "unbound", cwd: elsewhere, instructionMode: "append", options: { ...options, model: targetId(target) }, input },
    ];
    for (const start of starts) {
      const began = Date.now();
      await assert.rejects(provider.dispatch("thread/start", start), (error: any) => {
        assert.ok(error instanceof GasCityProjectRequiredError);
        assert.equal(error.name, "GasCityProjectRequiredError");
        assert.deepEqual(error.data, { kind: "gasCityProjectRequired" });
        assert.match(error.message, /Gas City needs a mapped BB project/);
        assert.match(error.message, /gc bb bind/);
        return true;
      });
      assert.ok(Date.now() - began < 1000, "refusal must not wait on Gas City");
    }
    const providerThreadId = `gcs1_${Buffer.from(JSON.stringify({ v: 1, target, sessionId: "s-legacy" })).toString("base64url")}`;
    await assert.rejects(provider.dispatch("thread/resume", { threadId: "personal-city", providerThreadId, cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target), providerOptions: { projectId: "proj_personal" } } }), GasCityProjectRequiredError);
    assert.equal(f.calls.length, 0, "no Gas City request is made for a Personal-project conversation");
    // BB receives a typed JSON-RPC error, not a hang.
    provider.handleLine(JSON.stringify({ jsonrpc: "2.0", id: 7, method: "thread/start", params: starts[0] }));
    await until(() => messages.some(m => m.id === 7));
    const reply = messages.find(m => m.id === 7);
    assert.equal(reply.error.code, -32000);
    assert.deepEqual(reply.error.data, { kind: "gasCityProjectRequired" });
    assert.match(reply.error.message, /Gas City needs a mapped BB project/);
    assert.equal(f.calls.length, 0);
  } finally { await provider.close(); await f.close(); await rm(elsewhere, { recursive: true, force: true }); }
});

test("startup without a GC directory blocks, then explicit retry reuses its unsent session", async () => {
  const f = await fixture(); const bbCwd = f.cwd;
  let reportDirectory = false;
  class DirectoryClient extends GasCityClient {
    override async getSession(city: string, id: string, signal?: AbortSignal) {
      const result = await super.getSession(city, id, signal);
      if (result.template && !reportDirectory) delete result.work_dir;
      return result;
    }
  }
  const messages: any[] = []; const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, client: c => new DirectoryClient(c), journal });
  try {
    const args = { threadId: "retry-workspace", cwd: bbCwd, instructionMode: "append", options: { ...options, model: targetId(target), providerOptions: { projectId: "project-web" } }, input: [{ type: "text", text: "hello?" }] };
    await assert.rejects(provider.dispatch("thread/start", args), /cannot verify workspace ownership/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    const receipt = await journal.get(args.threadId); assert.ok(receipt?.sessionId);
    assert.equal(receipt.turn, undefined);
    reportDirectory = true;
    const started: any = await provider.dispatch("thread/start", args);
    await until(() => messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "turn.boundary" && d.status === "completed"));
    assert.equal((await journal.get(args.threadId))?.sessionId, receipt.sessionId);
    assert.ok(started.providerThreadId);
    assert.equal(f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions")).length, 1);
    const submissions = f.calls.filter(c => c.path.endsWith("/submit")); assert.equal(submissions.length, 1);
    assert.equal(submissions[0]!.body.message.split("hello?").length - 1, 1);
    assert.ok(submissions[0]!.body.message.endsWith("hello?"));
  } finally { await provider.close(); await f.close(); }
});
