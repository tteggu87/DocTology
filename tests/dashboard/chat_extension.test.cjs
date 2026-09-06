const { test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const extensionPath = path.join(__dirname, '../../runtime/wiki_dashboard_chat_extension.mjs');
const names = ['wiki_list', 'wiki_search', 'wiki_read', 'wiki_links'];
const savedEnv = { url: process.env.WIKI_STUDIO_TOOL_URL, token: process.env.WIKI_STUDIO_TOOL_TOKEN, fetch: global.fetch };

beforeEach(() => {
  process.env.WIKI_STUDIO_TOOL_URL = 'http://127.0.0.1:43123/wiki-tools';
  process.env.WIKI_STUDIO_TOOL_TOKEN = 'test-secret-token';
});
afterEach(() => {
  if (savedEnv.url === undefined) delete process.env.WIKI_STUDIO_TOOL_URL; else process.env.WIKI_STUDIO_TOOL_URL = savedEnv.url;
  if (savedEnv.token === undefined) delete process.env.WIKI_STUDIO_TOOL_TOKEN; else process.env.WIKI_STUDIO_TOOL_TOKEN = savedEnv.token;
  global.fetch = savedEnv.fetch;
});
async function loadFactory() { return (await import(`${pathToFileURL(extensionPath).href}?test=${Date.now()}-${Math.random()}`)).default; }
function mockPi({ active = names, failSet = false } = {}) {
  const tools = new Map(), events = new Map(), setCalls = [];
  return {
    tools, events, setCalls,
    registerTool(tool) { tools.set(tool.name, tool); }, on(name, handler) { events.set(name, handler); },
    setActiveTools(next) { setCalls.push(next); if (failSet) throw new Error('activation failure'); active = [...next]; },
    getActiveTools() { return active; },
  };
}
function response(body, ok = true) { return { ok, json: async () => body }; }
function success(result) { return response({ ok: true, result }); }
function failure(error, { exhausted = false, limits = undefined } = {}) { return response({ ok: false, error, exhausted, limits }, false); }

test('registers exactly the four plain-schema read-only wiki tools', async () => {
  const pi = mockPi(); global.fetch = async () => success({}); (await loadFactory())(pi);
  assert.deepEqual([...pi.tools.keys()], names);
  for (const tool of pi.tools.values()) {
    assert.equal(tool.parameters.type, 'object'); assert.equal(tool.parameters.additionalProperties, false);
    assert.equal(Object.getOwnPropertySymbols(tool.parameters).length, 0); assert.equal(tool.executionMode, 'sequential');
  }
  assert.equal(pi.tools.get('wiki_list').parameters.properties.limit.maximum, 40);
  assert.equal(pi.tools.get('wiki_list').parameters.properties.scope.default, 'wiki');
  assert.equal(pi.tools.get('wiki_search').parameters.properties.limit.maximum, 12);
  assert.equal(pi.tools.get('wiki_search').parameters.properties.scope.default, 'all');
  assert.equal(pi.tools.get('wiki_read').parameters.properties.limit.maximum, 10000);
  assert.match(pi.tools.get('wiki_read').description, /citation/i);
});

test('session start forces the exact allowlist before an envelope-validated ready handshake', async () => {
  const pi = mockPi({ active: [] }); const calls = [];
  global.fetch = async (_url, options) => { calls.push(options); return success({ ready: true }); };
  (await loadFactory())(pi); await pi.events.get('session_start')({}, {});
  assert.deepEqual(pi.setCalls, [names]); assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(calls[0].body), { tool: 'ready', arguments: {} });
  assert.equal(calls[0].headers.authorization, 'Bearer test-secret-token'); assert.equal(calls[0].redirect, 'error');
});

test('invalid ready payload never confirms readiness', async () => {
  const pi = mockPi(); global.fetch = async () => success({ accepted: true }); (await loadFactory())(pi);
  await assert.rejects(pi.events.get('session_start')({}, {}), /readiness was not confirmed/);
});

test('failed activation prevents the ready handshake', async () => {
  const pi = mockPi({ failSet: true }); let requests = 0;
  global.fetch = async () => { requests += 1; return success({ ready: true }); };
  (await loadFactory())(pi);
  await assert.rejects(pi.events.get('session_start')({}, {}), /activation failure/); assert.equal(requests, 0);
});

test('tool-call guard blocks every non-wiki tool', async () => {
  const pi = mockPi(); global.fetch = async () => success({}); (await loadFactory())(pi);
  assert.deepEqual(await pi.events.get('tool_call')({ toolName: 'bash' }, {}), { block: true, reason: 'Only approved wiki tools are allowed.' });
  assert.equal(await pi.events.get('tool_call')({ toolName: 'wiki_read' }, {}), undefined);
});

test('unwraps the documented success envelope through the 64th tool call', async () => {
  const pi = mockPi(); let call = 0, last;
  global.fetch = async (url, options) => { call += 1; last = { url, options }; return success({ call, items: [{ path: 'wiki/index.md' }] }); };
  (await loadFactory())(pi);
  let result;
  for (let index = 0; index < 64; index += 1) result = await pi.tools.get('wiki_list').execute(`call-${index}`, { offset: index, limit: 1 }, undefined);
  assert.equal(call, 64); assert.equal(last.url, 'http://127.0.0.1:43123/wiki-tools'); assert.equal(last.options.method, 'POST'); assert.equal(last.options.redirect, 'error');
  assert.deepEqual(JSON.parse(last.options.body), { tool: 'wiki_list', arguments: { offset: 63, limit: 1 } });
  assert.deepEqual(result.details, { tool: 'wiki_list' }); assert.equal(JSON.parse(result.content[0].text).call, 64);
});

test('wrapped HTTP 429 preserves a trusted tool error and disables tools on exhausted budget', async () => {
  const pi = mockPi(); global.fetch = async () => failure('The approved exploration budget is exhausted.', { exhausted: true, limits: { calls: 64 } }); (await loadFactory())(pi);
  await assert.rejects(pi.tools.get('wiki_search').execute('call-429', { query: 'x' }, undefined), error =>
    error.message.includes('approved exploration budget') && error.message.includes('Conclude using only retrieved evidence') && error.message.includes('"calls":64'));
  assert.deepEqual(pi.setCalls, [[]]);
});

test('network failures and malformed envelopes remain redacted', async () => {
  const pi = mockPi(); global.fetch = async () => { throw new Error('network secret test-secret-token at 10.0.0.8'); }; (await loadFactory())(pi);
  await assert.rejects(pi.tools.get('wiki_search').execute('call-2', { query: 'x' }, undefined), error => error.message === 'Wiki bridge request failed.' && !error.message.includes('secret'));
  global.fetch = async () => response({ ok: true, result: null });
  await assert.rejects(pi.tools.get('wiki_search').execute('call-3', { query: 'x' }, undefined), /invalid response/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(pi.tools.get('wiki_search').execute('call-4', { query: 'x' }, controller.signal), /cancelled/);
});

test('successful nested exhaustion disables tools and tells the model to conclude with limits', async () => {
  const pi = mockPi(); global.fetch = async () => success({ exploration: { exhausted: true }, limits: { calls: 64 }, results: [] }); (await loadFactory())(pi);
  const result = await pi.tools.get('wiki_search').execute('call-4', { query: 'x' }, undefined);
  assert.deepEqual(pi.setCalls, [[]]); assert.match(result.content[0].text, /budget is exhausted/i); assert.match(result.content[0].text, /"calls":64/);
});

test('large escaped wiki reads preserve content and stable citation fields while dropping only metadata', async () => {
  const pi = mockPi();
  const content = '<section>& cited [7] '.repeat(500);
  const document = { path: 'wiki/evidence.md', content, number: 7, candidateNumber: 7, hash: 'abc123', ranges: [{ start: 0, end: content.length }], rawSources: Array.from({ length: 100 }, (_, index) => ({ id: index, text: 'x'.repeat(1000) })) };
  global.fetch = async () => success({ document }); (await loadFactory())(pi);
  const result = await pi.tools.get('wiki_read').execute('call-read', { path: 'wiki/evidence.md' }, undefined);
  const received = JSON.parse(result.content[0].text);
  assert.equal(received.document.content, content); assert.equal(received.document.number, 7); assert.equal(received.document.candidateNumber, 7);
  assert.equal(received.document.hash, 'abc123'); assert.deepEqual(received.document.ranges, document.ranges);
  assert.equal(received.document.rawSources, undefined); assert.equal(received.document.rawSourcesOmitted, true);
  assert.ok(result.content[0].text.length <= 64 * 1024);
});

test('oversized discovery lists are structurally truncated at item boundaries with nextOffset', async () => {
  const pi = mockPi();
  const items = Array.from({ length: 100 }, (_, index) => ({ id: index, path: `wiki/${index}.md`, title: `title-${index}`, excerpt: 'x'.repeat(1400) }));
  global.fetch = async () => success({ items }); (await loadFactory())(pi);
  const result = await pi.tools.get('wiki_list').execute('call-list', { offset: 10, limit: 40 }, undefined);
  const received = JSON.parse(result.content[0].text);
  assert.equal(received.truncated, true); assert.ok(received.items.length > 0 && received.items.length < items.length);
  assert.deepEqual(received.items, items.slice(0, received.items.length)); assert.equal(received.nextOffset, 10 + received.items.length);
  assert.ok(result.content[0].text.length <= 64 * 1024);
});

test('rejects non-loopback callback configuration', async () => {
  process.env.WIKI_STUDIO_TOOL_URL = 'https://127.0.0.1:43123/wiki-tools'; const pi = mockPi(); const factory = await loadFactory();
  assert.throws(() => factory(pi), /local HTTP port/);
});
