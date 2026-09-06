const { test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const extensionPath = path.join(__dirname, '../../runtime/wiki_dashboard_batch_extension.mjs');
const read = ['wiki_list', 'wiki_search', 'wiki_read', 'wiki_links'];
const worker = [...read, 'draft_write', 'draft_submit'];
const coordinator = [...read, 'wiki_prepare_batch'];
const saved = { url: process.env.WIKI_STUDIO_TOOL_URL, token: process.env.WIKI_STUDIO_TOOL_TOKEN, role: process.env.WIKI_STUDIO_BATCH_ROLE, fetch: global.fetch };
beforeEach(() => { process.env.WIKI_STUDIO_TOOL_URL = 'http://127.0.0.1:43123/wiki-tools'; process.env.WIKI_STUDIO_TOOL_TOKEN = 'secret'; });
afterEach(() => { for (const [key, value] of Object.entries({ WIKI_STUDIO_TOOL_URL: saved.url, WIKI_STUDIO_TOOL_TOKEN: saved.token, WIKI_STUDIO_BATCH_ROLE: saved.role })) value === undefined ? delete process.env[key] : process.env[key] = value; global.fetch = saved.fetch; });
async function load() { return (await import(`${pathToFileURL(extensionPath).href}?v=${Math.random()}`)).default; }
function pi(active = ['read', 'bash', 'write']) { const tools = new Map(), events = new Map(), sets = []; return { tools, events, sets, registerTool(t) { tools.set(t.name, t); }, on(n, h) { events.set(n, h); }, setActiveTools(v) { sets.push(v); active = [...v]; }, getActiveTools() { return active; } }; }
function response(body, ok = true) { return { ok, json: async () => body }; }
function success(result) { return response({ ok: true, result }); }
const prepared = { phase: 'prepared', batchId: 'batch-1', workers: [{ workerId: 'w1', source: 'raw/a.md', status: 'prepared', draftDir: 'drafts/w1', runId: 'run-1', attempt: 1 }, { workerId: 'w2', source: 'raw/b.md', status: 'prepared', draftDir: 'drafts/w2', runId: 'run-2', attempt: 1 }] };

test('worker exposes only read and draft tools and keeps builtins blocked', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'worker'; global.fetch = async () => success({ ready: true }); const p = pi(); (await load())(p);
  assert.deepEqual([...p.tools.keys()], worker); assert.match(p.tools.get('draft_write').description, /logical path wiki\/\.\.\.md/i); assert.match(p.tools.get('draft_write').description, /never prefix.*draftDir/i); await p.events.get('session_start')(); assert.deepEqual(p.sets, [worker]);
  assert.deepEqual(p.events.get('tool_call')({ toolName: 'bash' }), { block: true, reason: 'Only approved wiki batch tools are allowed.' });
  assert.equal(p.events.get('tool_call')({ toolName: 'draft_write' }), undefined);
});

test('coordinator locks original builtins until a valid prepared snapshot restores them', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'coordinator'; const calls = []; let status = 0;
  global.fetch = async (_url, options) => { const call = JSON.parse(options.body); calls.push(call); if (call.tool === 'ready') return success({ ready: true }); if (call.tool === 'batch_prepare') return success({ phase: 'preparing', batchId: 'batch-1', parallelism: 3, workers: [{ workerId: 'w1', source: 'raw/a.md', status: 'running' }, { workerId: 'w2', source: 'raw/b.md', status: 'pending' }] }); status += 1; return success(prepared); };
  const p = pi(); (await load())(p); assert.deepEqual([...p.tools.keys()], coordinator); await p.events.get('session_start')(); assert.deepEqual(p.sets, [coordinator]); assert.deepEqual(p.events.get('tool_call')({ toolName: 'write' }), { block: true, reason: 'Only approved wiki batch tools are allowed.' });
  const result = await p.tools.get('wiki_prepare_batch').execute('id', { plans: [{ source: 'raw/a.md', instructions: 'cover it' }, { source: 'raw/b.md', instructions: 'cover it too' }] });
  assert.equal(JSON.parse(result.content[0].text).phase, 'prepared'); assert.equal(status, 1); assert.deepEqual(p.sets.at(-1), ['read', 'bash', 'write']); assert.equal(p.events.get('tool_call')({ toolName: 'write' }), undefined); assert.deepEqual(p.events.get('tool_call')({ toolName: 'wiki_list' }), { block: true, reason: 'Only approved wiki batch tools are allowed.' }); assert.deepEqual(p.events.get('tool_call')({ toolName: 'wiki_prepare_batch' }), { block: true, reason: 'Only approved wiki batch tools are allowed.' }); assert.deepEqual(calls.map((x) => x.tool), ['ready', 'batch_prepare', 'batch_status']);
});

test('failed, malformed, premature, or mismatched prepared snapshots never unlock coordinator builtins', async () => {
  const invalid = [
    { phase: 'stopped', batchId: 'b', workers: [] },
    { phase: 'prepared', batchId: '', workers: [] },
    { phase: 'prepared', batchId: 'b', workers: [{ source: 'x', status: 'failed' }] },
    { phase: 'prepared', batchId: 'b', workers: [{ source: 'x', status: 'pending' }] },
    { phase: 'prepared', batchId: 'b', workers: [] },
    { phase: 'prepared', batchId: 'b', workers: [{ source: 'x', status: 'prepared' }, { source: 'extra', status: 'prepared' }] },
  ];
  for (const result of invalid) {
    process.env.WIKI_STUDIO_BATCH_ROLE = 'coordinator'; global.fetch = async (_url, options) => JSON.parse(options.body).tool === 'ready' ? success({ ready: true }) : success(result);
    const p = pi(); (await load())(p); await p.events.get('session_start')(); await assert.rejects(p.tools.get('wiki_prepare_batch').execute('id', { plans: [{ source: 'x', instructions: 'y' }] })); assert.deepEqual(p.sets, [coordinator]); assert.deepEqual(p.events.get('tool_call')({ toolName: 'write' }), { block: true, reason: 'Only approved wiki batch tools are allowed.' });
  }
});

test('abort prevents a late prepared response from unlocking tools and requests remain bounded', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'coordinator'; const controller = new AbortController();
  global.fetch = async (_url, options) => { const tool = JSON.parse(options.body).tool; if (tool === 'ready') return success({ ready: true }); if (tool === 'batch_prepare') { controller.abort(); return success(prepared); } throw new Error('unexpected'); };
  const p = pi(); (await load())(p); await p.events.get('session_start')(); await assert.rejects(p.tools.get('wiki_prepare_batch').execute('id', { plans: [{ source: 'x', instructions: 'y' }] }, controller.signal), /cancelled/); assert.deepEqual(p.sets, [coordinator]);
});

test('requires a valid role and loopback configuration', async () => {
  const factory = await load(); delete process.env.WIKI_STUDIO_BATCH_ROLE; const p = pi(); assert.throws(() => factory(p), /role/);
  process.env.WIKI_STUDIO_BATCH_ROLE = 'worker'; process.env.WIKI_STUDIO_TOOL_URL = 'http://localhost:43123/x'; assert.throws(() => factory(p), /local HTTP port/);
});

test('read results use the shared bounded bridge formatter without changing text', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'worker'; const content = '<x>'.repeat(5000); global.fetch = async (_url, options) => JSON.parse(options.body).tool === 'wiki_read' ? success({ document: { path: 'wiki/a.md', content, number: 9, hash: 'h' } }) : success({ ready: true }); const p = pi(); (await load())(p); const out = await p.tools.get('wiki_read').execute('id', { path: 'wiki/a.md' }); assert.equal(JSON.parse(out.content[0].text).document.content, content);
});


test('a mismatched poll batch id or worker set never unlocks coordinator tools', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'coordinator';
  global.fetch = async (_url, options) => {
    const tool = JSON.parse(options.body).tool;
    if (tool === 'ready') return success({ ready: true });
    if (tool === 'batch_prepare') return success({ phase: 'preparing', batchId: 'batch-a', workers: [{ source: 'x', status: 'running' }] });
    return success({ phase: 'prepared', batchId: 'batch-b', workers: [{ source: 'x', status: 'prepared' }] });
  };
  const p = pi(); (await load())(p); await p.events.get('session_start')();
  await assert.rejects(p.tools.get('wiki_prepare_batch').execute('id', { plans: [{ source: 'x', instructions: 'y' }] }), /invalid batch status/);
  assert.deepEqual(p.sets, [coordinator]);
});

test('oversized preparation snapshots retain worker integration pointers', async () => {
  process.env.WIKI_STUDIO_BATCH_ROLE = 'coordinator';
  const workers = Array.from({ length: 12 }, (_, index) => ({ source: `s${index}`, status: 'prepared', draftDir: `drafts/${index}`, runId: `run-${index}`, attempt: index + 1, metadata: 'x'.repeat(10000) }));
  global.fetch = async (_url, options) => JSON.parse(options.body).tool === 'ready' ? success({ ready: true }) : success({ phase: 'prepared', batchId: 'b', workers });
  const p = pi(); (await load())(p); await p.events.get('session_start')();
  const out = await p.tools.get('wiki_prepare_batch').execute('id', { plans: workers.map((item) => ({ source: item.source, instructions: 'y' })) });
  const parsed = JSON.parse(out.content[0].text); assert.equal(parsed.workers.length, 12); assert.deepEqual(parsed.workers[0], { source: 's0', status: 'prepared', draftDir: 'drafts/0', runId: 'run-0', attempt: 1 }); assert.ok(out.content[0].text.length <= 64 * 1024);
});
