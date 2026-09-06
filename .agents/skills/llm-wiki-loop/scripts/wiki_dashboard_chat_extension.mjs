const TOOL_NAMES = ["wiki_list", "wiki_search", "wiki_read", "wiki_links"];
const TOOL_SET = new Set(TOOL_NAMES);
const REQUEST_TIMEOUT_MS = 15_000;
const MAX_RESULT_CHARS = 64 * 1024;
const DISCOVERY_ARRAY_KEYS = ["items", "results", "documents", "pages"];
const READ_DOCUMENT_CORE_KEYS = new Set(["path", "content", "text", "number", "candidateNumber", "hash", "ranges"]);

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

export function objectSchema(properties, required) {
  return { type: "object", properties, required, additionalProperties: false };
}
function isRecord(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function isExhausted(value) { return value?.exhausted === true || value?.exploration?.exhausted === true; }
function jsonText(value) {
  try { const text = JSON.stringify(value); return typeof text === "string" ? text : "null"; }
  catch { return JSON.stringify({ error: "Wiki bridge returned an unreadable result." }); }
}
function fits(value) { return jsonText(value).length <= MAX_RESULT_CHARS; }
function cloneResult(result) { return { ...result }; }

function boundDiscoveryResult(result, arguments_) {
  const bounded = cloneResult(result);
  const key = DISCOVERY_ARRAY_KEYS.find((candidate) => Array.isArray(bounded[candidate]));
  if (!key || fits(bounded)) return bounded;
  const original = bounded[key];
  const kept = [];
  for (const item of original) {
    const candidate = { ...bounded, [key]: [...kept, item] };
    if (!fits(candidate)) break;
    kept.push(item);
  }
  bounded[key] = kept;
  bounded.truncated = true;
  if (bounded.nextOffset === undefined && Number.isInteger(arguments_?.offset)) {
    bounded.nextOffset = arguments_.offset + kept.length;
  }
  return bounded;
}

function boundReadResult(result) {
  const bounded = cloneResult(result);
  if (!isRecord(bounded.document) || fits(bounded)) return bounded;
  const document = { ...bounded.document };
  if (Object.prototype.hasOwnProperty.call(document, "rawSources")) {
    delete document.rawSources;
    document.rawSourcesOmitted = true;
  }
  if (Object.prototype.hasOwnProperty.call(bounded, "rawSources")) {
    delete bounded.rawSources;
    bounded.rawSourcesOmitted = true;
  }
  bounded.document = document;
  if (fits(bounded)) return bounded;
  const coreDocument = {};
  for (const key of READ_DOCUMENT_CORE_KEYS) {
    if (Object.prototype.hasOwnProperty.call(document, key)) coreDocument[key] = document[key];
  }
  coreDocument.metadataOmitted = true;
  const coreResult = { document: coreDocument, metadataOmitted: true };
  for (const key of ["exhausted", "limits", "truncated", "nextOffset"]) {
    if (Object.prototype.hasOwnProperty.call(bounded, key)) coreResult[key] = bounded[key];
  }
  return coreResult;
}

export function boundedResult(tool, result, arguments_) {
  return jsonText(tool === "wiki_read" ? boundReadResult(result) : boundDiscoveryResult(result, arguments_));
}
function exactToolSet(active) {
  return Array.isArray(active) && active.length === TOOL_NAMES.length &&
    active.every((name) => TOOL_SET.has(name)) && new Set(active).size === TOOL_NAMES.length;
}
function combinedSignal(signal) {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}
function safeErrorText(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 1_000
    ? value : "Wiki bridge request was rejected.";
}

export const READ_TOOL_DEFINITIONS = Object.freeze([
  Object.freeze({ name: "wiki_list", description: "List or index the approved wiki inventory for an overview. Discovered documents are not read evidence; use wiki_read before citing.", parameters: objectSchema({ offset: { type: "integer", minimum: 0, default: 0 }, limit: { type: "integer", minimum: 1, maximum: 40, default: 40 }, scope: { type: "string", enum: ["wiki", "raw", "all"], default: "wiki" }, filter: { type: "string" } }, []) }),
  Object.freeze({ name: "wiki_search", description: "Search the approved inventory. Reformulate searches when needed, then follow links or read pages. Search discoveries are not citations.", parameters: objectSchema({ query: { type: "string", minLength: 1 }, limit: { type: "integer", minimum: 1, maximum: 12, default: 12 }, scope: { type: "string", enum: ["wiki", "raw", "all"], default: "all" } }, ["query"]) }),
  Object.freeze({ name: "wiki_read", description: "Read an approved page. Only wiki_read numbered passages are stable per-document citation evidence; cite only those numbers.", parameters: objectSchema({ path: { type: "string", minLength: 1 }, offset: { type: "integer", minimum: 0, default: 0 }, limit: { type: "integer", minimum: 1, maximum: 10000, default: 10000 } }, ["path"]) }),
  Object.freeze({ name: "wiki_links", description: "Follow links from an approved page to find relevant documents. Linked or discovered documents must be wiki_read before citation.", parameters: objectSchema({ path: { type: "string", minLength: 1 } }, ["path"]) }),
]);

export default function wikiDashboardChatExtension(pi) {
  const config = callbackConfig();
  const disableForBudget = () => pi.setActiveTools([]);
  const exhaustionMessage = (limits) => {
    const suffix = limits === undefined ? "" : `\nLimits: ${jsonText({ limits })}`;
    return `Wiki exploration budget is exhausted. Conclude using only retrieved evidence and state the remaining limits.${suffix}`;
  };

  async function callBridge(tool, arguments_, signal) {
    if (signal?.aborted) throw new Error("Wiki bridge request cancelled.");
    let response, envelope;
    try {
      response = await fetch(config.url, {
        method: "POST", redirect: "error", signal: combinedSignal(signal),
        headers: { "content-type": "application/json", authorization: `Bearer ${config.token}` },
        body: JSON.stringify({ tool, arguments: arguments_ }),
      });
      envelope = await response.json();
    } catch { throw new Error("Wiki bridge request failed."); }
    if (!isRecord(envelope) || typeof envelope.ok !== "boolean") {
      throw new Error("Wiki bridge returned an invalid response.");
    }
    if (envelope.ok === true) {
      if (!response.ok || !isRecord(envelope.result)) throw new Error("Wiki bridge returned an invalid response.");
      return { ok: true, result: envelope.result };
    }
    if (response.ok || !Object.prototype.hasOwnProperty.call(envelope, "error")) {
      throw new Error("Wiki bridge returned an invalid response.");
    }
    return { ok: false, error: safeErrorText(envelope.error), exhausted: isExhausted(envelope), limits: envelope.limits };
  }

  async function execute(tool, arguments_, signal) {
    const bridge = await callBridge(tool, arguments_, signal);
    if (!bridge.ok) {
      if (bridge.exhausted) {
        disableForBudget();
        throw new Error(`${bridge.error}\n${exhaustionMessage(bridge.limits)}`);
      }
      throw new Error(bridge.error);
    }
    const result = bridge.result;
    let text = boundedResult(tool, result, arguments_);
    if (isExhausted(result)) {
      disableForBudget();
      text = `${exhaustionMessage(result.limits)}\n${text}`;
    }
    return { content: [{ type: "text", text }], details: { tool } };
  }

  for (const definition of READ_TOOL_DEFINITIONS) {
    pi.registerTool({ ...definition, label: definition.name, executionMode: "sequential", async execute(_toolCallId, arguments_, signal) { return execute(definition.name, arguments_, signal); } });
  }
  pi.on("tool_call", (event) => {
    if (!TOOL_SET.has(event.toolName)) return { block: true, reason: "Only approved wiki tools are allowed." };
  });
  pi.on("session_start", async () => {
    pi.setActiveTools(TOOL_NAMES);
    if (!exactToolSet(pi.getActiveTools())) throw new Error("Wiki tool activation verification failed.");
    const ready = await callBridge("ready", {}, undefined);
    if (!ready.ok || ready.result.ready !== true) throw new Error("Wiki bridge readiness was not confirmed.");
  });
}
