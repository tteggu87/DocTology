import { READ_TOOL_DEFINITIONS, boundedResult, objectSchema } from "./wiki_dashboard_chat_extension.mjs";

const READ_NAMES = READ_TOOL_DEFINITIONS.map((tool) => tool.name);
const WORKER_NAMES = [...READ_NAMES, "draft_write", "draft_submit"];
const COORDINATOR_NAMES = [...READ_NAMES, "wiki_prepare_batch"];
const REQUEST_TIMEOUT_MS = 15_000;
const POLL_MS = 500;
const MAX_RESULT_CHARS = 64 * 1024;

function isRecord(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function jsonText(value) {
  try { const text = JSON.stringify(value); return typeof text === "string" ? text : "null"; }
  catch { return JSON.stringify({ error: "Wiki bridge returned an unreadable result." }); }
}
function safeErrorText(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 1_000
    ? value : "Wiki bridge request was rejected.";
}
function callbackConfig() {
  const urlText = process.env.WIKI_STUDIO_TOOL_URL;
  const token = process.env.WIKI_STUDIO_TOOL_TOKEN;
  if (!urlText || !token) throw new Error("Wiki bridge configuration is required.");
  let url;
  try { url = new URL(urlText); } catch { throw new Error("Wiki bridge URL is invalid."); }
  const port = Number(url.port);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port ||
    !Number.isInteger(port) || port < 1 || port > 65535 ||
    url.username || url.password || url.search || url.hash) {
    throw new Error("Wiki bridge URL must be a local HTTP port.");
  }
  return { url: url.toString(), token };
}
function roleConfig() {
  const role = process.env.WIKI_STUDIO_BATCH_ROLE;
  if (role !== "worker" && role !== "coordinator") throw new Error("Wiki batch role must be worker or coordinator.");
  return role;
}
function combinedSignal(signal) {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}
function exactTools(pi, names) {
  const active = pi.getActiveTools();
  return Array.isArray(active) && active.length === names.length &&
    active.every((name) => names.includes(name)) && new Set(active).size === names.length;
}
function assertNotAborted(signal) {
  if (signal?.aborted) throw new Error("Wiki bridge request cancelled.");
}
function waitForPoll(signal) {
  assertNotAborted(signal);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(done, POLL_MS);
    function done() { signal?.removeEventListener("abort", cancel); resolve(); }
    function cancel() { clearTimeout(timer); reject(new Error("Wiki bridge request cancelled.")); }
    signal?.addEventListener("abort", cancel, { once: true });
    if (signal?.aborted) cancel();
  });
}
function boundedOperationResult(result) {
  const shallow = { ...result };
  for (const key of ["content", "text", "draft", "draftContent", "planContent"]) delete shallow[key];
  if (jsonText(shallow).length <= MAX_RESULT_CHARS) return jsonText(shallow);
  const workers = Array.isArray(result.workers) ? result.workers.map((worker) => isRecord(worker)
    ? Object.fromEntries(["id", "workerId", "source", "status", "phase", "draftDir", "runId", "attempt", "draft_dir", "run_id"].filter((key) => worker[key] !== undefined).map((key) => [key, worker[key]]))
    : {}) : undefined;
  const compact = { metadataOmitted: true };
  for (const key of ["phase", "batchId", "status", "draftId", "path", "submitted", "accepted", "pointer"]) {
    if (result[key] !== undefined) compact[key] = result[key];
  }
  if (workers !== undefined) compact.workers = workers;
  let text = jsonText(compact);
  if (text.length <= MAX_RESULT_CHARS) return text;
  return JSON.stringify({ phase: typeof result.phase === "string" ? result.phase : "unknown", batchId: typeof result.batchId === "string" ? result.batchId : undefined, metadataOmitted: true, truncated: true });
}
function validSnapshot(result, expectedSources, expectedBatchId) {
  if (!isRecord(result) || !["planning", "preparing", "prepared", "needs_attention", "stopped"].includes(result.phase) ||
    typeof result.batchId !== "string" || result.batchId.length === 0 || !Array.isArray(result.workers) ||
    (expectedBatchId !== undefined && result.batchId !== expectedBatchId)) return false;
  const seenSources = new Set();
  for (const worker of result.workers) {
    if (!isRecord(worker) || typeof worker.source !== "string" || !expectedSources.has(worker.source) || seenSources.has(worker.source)) return false;
    seenSources.add(worker.source);
  }
  if (result.workers.length !== expectedSources.size || expectedSources.size === 0 ||
    !result.workers.every((worker) => typeof worker.status === "string" && worker.status.length > 0)) return false;
  if (result.phase !== "prepared") return true;
  return result.workers.every((worker) => worker.status === "prepared");
}
function preparationBudgetMs(snapshot, sourceCount) {
  const parallelism = Number.isInteger(snapshot.parallelism) ? Math.min(4, Math.max(1, snapshot.parallelism)) : 3;
  return Math.min(48 * 60 * 1000, Math.ceil(sourceCount / parallelism) * 12 * 60 * 1000);
}

export default function wikiDashboardBatchExtension(pi) {
  const config = callbackConfig();
  const role = roleConfig();
  const allowed = role === "worker" ? WORKER_NAMES : COORDINATOR_NAMES;
  const allowedSet = new Set(allowed);
  let handoff = false;
  let originalBuiltins = [];

  async function callBridge(tool, arguments_, signal) {
    assertNotAborted(signal);
    let response, envelope;
    try {
      response = await fetch(config.url, {
        method: "POST", redirect: "error", signal: combinedSignal(signal),
        headers: { "content-type": "application/json", authorization: `Bearer ${config.token}` },
        body: JSON.stringify({ tool, arguments: arguments_ }),
      });
      envelope = await response.json();
    } catch {
      if (signal?.aborted) throw new Error("Wiki bridge request cancelled.");
      throw new Error("Wiki bridge request failed.");
    }
    if (!isRecord(envelope) || typeof envelope.ok !== "boolean") throw new Error("Wiki bridge returned an invalid response.");
    if (envelope.ok === true) {
      if (!response.ok || !isRecord(envelope.result)) throw new Error("Wiki bridge returned an invalid response.");
      return { ok: true, result: envelope.result };
    }
    if (response.ok || !Object.prototype.hasOwnProperty.call(envelope, "error")) throw new Error("Wiki bridge returned an invalid response.");
    return { ok: false, error: safeErrorText(envelope.error) };
  }
  async function executeRead(tool, arguments_, signal) {
    const bridge = await callBridge(tool, arguments_, signal);
    if (!bridge.ok) throw new Error(bridge.error);
    return { content: [{ type: "text", text: boundedResult(tool, bridge.result, arguments_) }], details: { tool } };
  }
  async function executeDraft(tool, arguments_, signal) {
    const bridge = await callBridge(tool, arguments_, signal);
    if (!bridge.ok) throw new Error(bridge.error);
    return { content: [{ type: "text", text: boundedOperationResult(bridge.result) }], details: { tool } };
  }
  function restoreCoordinatorTools(signal) {
    assertNotAborted(signal);
    const restored = [...originalBuiltins];
    pi.setActiveTools(restored);
    if (!exactTools(pi, restored)) throw new Error("Wiki tool activation verification failed.");
    handoff = true;
  }
  async function executePrepare(_toolCallId, arguments_, signal) {
    const plans = arguments_?.plans;
    if (!Array.isArray(plans) || plans.length === 0 || plans.length > 12 ||
      plans.some((plan) => !isRecord(plan) || typeof plan.source !== "string" || plan.source.length === 0)) {
      throw new Error("Wiki batch preparation requires one to twelve valid source plans.");
    }
    const expectedSources = new Set(plans.map((plan) => plan.source));
    if (expectedSources.size !== plans.length) throw new Error("Wiki batch preparation requires unique plan sources.");
    const started = Date.now();
    let bridge = await callBridge("batch_prepare", arguments_, signal);
    if (!bridge.ok) throw new Error(bridge.error);
    assertNotAborted(signal);
    let snapshot = bridge.result;
    if (!validSnapshot(snapshot, expectedSources)) throw new Error("Wiki bridge returned an invalid batch status.");
    const batchId = snapshot.batchId;
    const budget = preparationBudgetMs(snapshot, expectedSources.size);
    while (snapshot.phase === "planning" || snapshot.phase === "preparing") {
      if (Date.now() - started >= budget) throw new Error("Wiki batch preparation timed out.");
      await waitForPoll(signal);
      bridge = await callBridge("batch_status", {}, signal);
      if (!bridge.ok) throw new Error(bridge.error);
      assertNotAborted(signal);
      snapshot = bridge.result;
      if (!validSnapshot(snapshot, expectedSources, batchId)) throw new Error("Wiki bridge returned an invalid batch status.");
    }
    assertNotAborted(signal);
    if (snapshot.phase === "prepared") restoreCoordinatorTools(signal);
    if (snapshot.phase === "needs_attention" || snapshot.phase === "stopped") {
      throw new Error(`Wiki batch preparation ended with status: ${snapshot.phase}.`);
    }
    return { content: [{ type: "text", text: boundedOperationResult(snapshot) }], details: { tool: "wiki_prepare_batch" } };
  }

  for (const definition of READ_TOOL_DEFINITIONS) {
    pi.registerTool({ ...definition, label: definition.name, executionMode: "sequential", async execute(_toolCallId, arguments_, signal) { return executeRead(definition.name, arguments_, signal); } });
  }
  if (role === "worker") {
    pi.registerTool({ name: "draft_write", label: "draft_write", description: "Write a proposed wiki Markdown draft only at logical path wiki/...md. Never prefix it with an assigned state draftDir; the host adds the files directory. This cannot write canonical wiki files.", executionMode: "sequential", parameters: objectSchema({ path: { type: "string", pattern: "^wiki/.+\\.md$" }, content: { type: "string" } }, ["path", "content"]), async execute(_id, arguments_, signal) { return executeDraft("draft_write", arguments_, signal); } });
    pi.registerTool({ name: "draft_submit", label: "draft_submit", description: "Submit the bounded worker draft plan for coordinator review.", executionMode: "sequential", parameters: objectSchema({ summary: { type: "string" }, plan: { type: "string" } }, ["summary", "plan"]), async execute(_id, arguments_, signal) { return executeDraft("draft_submit", arguments_, signal); } });
  } else {
    const questionCase = objectSchema({ id: { type: "string" }, question: { type: "string" }, required: { type: "boolean" }, expected_posture: { type: "string" } }, ["id", "question", "required", "expected_posture"]);
    const questions = objectSchema({ schema_version: { const: 1 }, cases: { type: "array", items: questionCase } }, ["schema_version", "cases"]);
    pi.registerTool({ name: "wiki_prepare_batch", label: "wiki_prepare_batch", description: "Prepare bounded worker drafts and return only when the batch is prepared or needs attention.", executionMode: "sequential", parameters: objectSchema({ plans: { type: "array", minItems: 1, maxItems: 12, items: objectSchema({ source: { type: "string" }, instructions: { type: "string" } }, ["source", "instructions"]) }, questions }, ["plans"]), execute: executePrepare });
  }
  pi.on("tool_call", (event) => {
    if (role === "coordinator" && handoff) {
      if (originalBuiltins.includes(event.toolName)) return undefined;
    } else if (allowedSet.has(event.toolName)) return undefined;
    return { block: true, reason: "Only approved wiki batch tools are allowed." };
  });
  pi.on("session_start", async () => {
    if (role === "coordinator") originalBuiltins = pi.getActiveTools().filter((name) => !allowedSet.has(name));
    pi.setActiveTools(allowed);
    if (!exactTools(pi, allowed)) throw new Error("Wiki tool activation verification failed.");
    const ready = await callBridge("ready", {}, undefined);
    if (!ready.ok || ready.result.ready !== true) throw new Error("Wiki bridge readiness was not confirmed.");
  });
}

export { READ_NAMES, WORKER_NAMES, COORDINATOR_NAMES };
