const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.join(__dirname, '../dashboard');
const moduleFiles = ['modules/retrieval-usage.js','modules/history-codec.js','modules/markdown.js','modules/graph.js','modules/retrieval-status.js'];

function moduleContext() {
  const sandbox = vm.createContext({console,URL,TextEncoder});
  for (const file of moduleFiles) vm.runInContext(fs.readFileSync(path.join(assets,file),'utf8'), sandbox, {filename:file});
  return sandbox;
}

test('frontend factories load without app or DOM globals',()=>{
  const sandbox=moduleContext();
  assert.equal('document' in sandbox,false);
  assert.equal('state' in sandbox,false);
  assert.deepEqual(Object.keys(sandbox.WikiStudioModules).sort(),['createGraphTools','createHistoryCodec','createMarkdownRenderer','createRetrievalStatusTools','createRetrievalUsage']);
  const usage=sandbox.WikiStudioModules.createRetrievalUsage({escapeHTML:value=>String(value)});
  assert.equal(usage.normalize({version:1,basis:'successful_discovery_calls',counts:{grep:2,fts:1,wikilinks:0,vector:0},listCalls:1,readCalls:1,unsupported:['wikilinks','vector']}).counts.grep,2);
  const graph=sandbox.WikiStudioModules.createGraphTools({escapeHTML:value=>String(value)});
  assert.deepEqual([...graph.citationFocus({nodes:[{id:'a'},{id:'b'}],edges:[{source:'a',target:'b'}],references:[{id:'a'}]}).pathNodes].sort(),['a','b']);
});

test('markdown, history, and graph factories receive all dependencies explicitly',()=>{
  const sandbox=moduleContext(),modules=sandbox.WikiStudioModules;
  const markdown=modules.createMarkdownRenderer({escapeHTML:value=>String(value).replace(/</g,'&lt;'),knownDocumentIds:()=>new Set(['wiki/a.md'])});
  assert.match(markdown.renderMarkdown('[A](wiki/a.md)'),/data-page="wiki\/a.md"/);
  const usage=modules.createRetrievalUsage({escapeHTML:value=>String(value)});
  const codec=modules.createHistoryCodec({limits:{conversations:2,messages:2,messageText:10,evidence:2,excerpt:10,explorationEvents:2,explorationText:10,storageBytes:300},byteSize:value=>Buffer.byteLength(value),normalizeRetrievalUsage:usage.normalize,now:()=>10});
  assert.equal(codec.normalizeConversation({messages:[{role:'assistant',content:'x'.repeat(20)}]}).messages[0].content.length,10);
  const layout=modules.createGraphTools({escapeHTML:value=>String(value)}).normalizePositions(new Map([['a',{x:0,y:0}],['b',{x:1,y:1}]]),[{id:'a'},{id:'b'}],340,300);
  assert.ok(layout.get('a').x>=32 && layout.get('b').x<=308);
});

test('deferred production order cold-boots once through external boot',async()=>{
  const elements=new Map();
  const element=name=>{if(!elements.has(name)){const classes=new Set();elements.set(name,{innerHTML:'',textContent:'',hidden:false,disabled:false,value:'',open:false,classList:{toggle(value,on){if(on===undefined?!classes.has(value):on)classes.add(value);else classes.delete(value);},add(value){classes.add(value);},remove(value){classes.delete(value);},contains(value){return classes.has(value);}},addEventListener(){},setAttribute(){},removeAttribute(){},focus(){},showModal(){this.open=true;},close(){this.open=false;},querySelector:selector=>element(name+' '+selector),querySelectorAll:()=>[]});}return elements.get(name);};
  const intervals=[],calls=[],example=JSON.parse(fs.readFileSync(path.join(assets,'example.json'),'utf8'));
  const document={querySelector:element,querySelectorAll:()=>[],addEventListener(){},body:element('body'),hidden:false};
  const sandbox=vm.createContext({document,console,URL,TextEncoder,localStorage:{getItem(){return null;},setItem(){},removeItem(){}},confirm:()=>true,clearTimeout(){},setTimeout(){return 1;},setInterval(callback,delay){intervals.push([callback,delay]);return intervals.length;},fetch:async(url)=>{calls.push(url);return {ok:true,json:async()=>url==='/api/session'?{token:'test-token'}:example};}});
  const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  const scripts=[...html.matchAll(/<script src="([^"]+)" defer><\/script>/g)].map(match=>match[1]);
  assert.deepEqual(scripts,[...moduleFiles.map(file=>'/'+file),'/app.js','/boot.js']);
  for(const src of scripts)vm.runInContext(fs.readFileSync(path.join(assets,src.slice(1)),'utf8'),sandbox,{filename:src});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sandbox.WikiStudioApp.started,true);
  assert.deepEqual(calls,['/api/session','/api/state']);
  assert.deepEqual(intervals.map(([,delay])=>delay),[2500]);
  vm.runInContext(fs.readFileSync(path.join(assets,'boot.js'),'utf8'),sandbox,{filename:'/boot.js repeat'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(calls,['/api/session','/api/state']);
  assert.deepEqual(intervals.map(([,delay])=>delay),[2500]);
});

test('every exported module helper runs with only injected dependencies',()=>{
  const sandbox=moduleContext(),modules=sandbox.WikiStudioModules;
  const escapeHTML=value=>String(value).replace(/[<>&"]/g, character=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[character]));
  const elements=new Map();
  const $=selector=>{
    if(!elements.has(selector)) elements.set(selector,{innerHTML:'',textContent:''});
    return elements.get(selector);
  };
  const usage=modules.createRetrievalUsage({escapeHTML});
  const normalizedUsage=usage.normalize({version:1,basis:'successful_discovery_calls',counts:{grep:2,fts:1,wikilinks:0,vector:0},results:{grep:3,fts:1,wikilinks:0,vector:0},listCalls:1,readCalls:1,unsupported:['wikilinks','vector']});
  assert.equal(usage.lanes.length,4);
  assert.equal(usage.retrievalUsageShares(normalizedUsage.counts).grep,67);
  assert.match(usage.render(normalizedUsage),/성공한 검색·링크 호출 3회/);
  assert.match(usage.renderCandidates([{title:'<candidate>'}],{}),/&lt;candidate&gt;/);
  assert.equal(usage.explorationEventLabel({tool:'wiki_read',path:'wiki/a.md',count:4}),'경로: wiki/a.md · 4자');
  assert.match(usage.renderExploration({calls:1,readCount:1,events:[{tool:'wiki_read',path:'wiki/a.md',count:4}],limits:null,invalidatedReadCount:0,exhausted:false}),/wiki_read/);

  const codec=modules.createHistoryCodec({limits:{conversations:2,messages:2,messageText:10,evidence:2,excerpt:10,explorationEvents:2,explorationText:10,storageBytes:500},byteSize:value=>Buffer.byteLength(value),normalizeRetrievalUsage:usage.normalize,now:()=>10});
  assert.deepEqual(JSON.parse(JSON.stringify(codec.normalizeReadRanges([{offset:0,end:2},{offset:-1,end:2}]))),[{offset:0,end:2}]);
  assert.equal(codec.normalizeContentHash('a'.repeat(64)),'a'.repeat(64));
  assert.equal(codec.normalizeReference({id:'wiki/a.md'},0).title,'wiki/a.md');
  assert.equal(codec.normalizeReferences([{id:'a'}]).length,1);
  assert.equal(codec.normalizeSaved({itemId:'i',sourcePath:'raw/a.md'}).scope,'answer');
  assert.equal(codec.normalizeExploration({calls:1,readCount:1,events:[],retrievalUsage:normalizedUsage}).calls,1);
  assert.equal(codec.normalizeConversation({messages:[{role:'user',content:'hello'}]}).messages.length,1);
  assert.ok(codec.buildHistoryPayload([{id:'a',updatedAt:1,messages:[]}],'a').bytes>0);
  assert.deepEqual(JSON.parse(JSON.stringify(codec.chatHistoryPayload([{role:'user',content:'x'}]))),[{role:'user',content:'x'}]);
  assert.equal(codec.boundedText('abc',2),'ab');
  assert.equal(codec.boundedCount(-1),0);

  const markdown=modules.createMarkdownRenderer({escapeHTML,knownDocumentIds:()=>new Set(['wiki/a.md'])});
  assert.equal(markdown.resolveInternalLink('wiki/a.md'), 'wiki/a.md');
  assert.match(markdown.renderInline('[[wiki/a|A]]'),/data-page="wiki\/a.md"/);
  assert.match(markdown.renderMarkdown('# Title'),/<h1>Title<\/h1>/);
  assert.match(markdown.renderAnswerMarkdown('See [1]',[{id:'wiki/a.md',number:1}]),/citation-link/);
  assert.equal(markdown.suggestedPrompts([{id:'wiki/a.md',title:'A'}]).length,1);
  assert.match(markdown.renderEmptyChat({name:'Vault',graph:{nodes:[]}},()=>''),/위키를 연결하면/);

  const graph=modules.createGraphTools({escapeHTML});
  const graphInput={nodes:[{id:'a',title:'A'},{id:'b',title:'B'}],edges:[{source:'a',target:'b'}],references:[{id:'a',number:1}]};
  assert.equal(graph.edgeKey('a','b'),graph.edgeKey('b','a'));
  assert.equal(graph.citationFocus(graphInput).pathEdges.size,1);
  const positioned=graph.positions(graphInput.nodes,graphInput.edges,340,300);
  assert.equal(positioned.size,2);
  assert.equal(graph.normalizePositions(positioned,graphInput.nodes,340,300).size,2);
  graph.renderKnowledgeGraph({state:{graph:{nodes:graphInput.nodes,edges:graphInput.edges}},references:graphInput.references,$,limit:80});
  assert.match($('#knowledge-graph').innerHTML,/knowledge-node/);

  const status=modules.createRetrievalStatusTools({escapeHTML});
  const fixture={version:1,root:'/vault',checkedAt:1,sqlite:{configured:true,state:'current',freshness:'stat',pages:2,chunks:3,fts:true,reasons:[]},onnx:{state:'configured',packages:{onnxruntime:true,tokenizers:true,numpy:true},modelConfigured:true,modelPresent:true,tokenizerConfigured:true,tokenizerPresent:true},vectors:{state:'stored',rows:2},chatMethods:{grep:true,fts:false,wikilinks:true,vector:false}};
  const normalizedStatus=status.normalizeRetrievalStatus(fixture,'/vault');
  assert.equal(normalizedStatus.sqlite.pages,2);
  status.renderRetrievalStatus({state:{root:'/vault'},retrievalStatus:normalizedStatus,retrievalStatusRoot:'/vault',$});
  assert.match($('#retrieval-readiness').innerHTML,/SQLite/);
  assert.match($('#retrieval-status-body').innerHTML,/ONNX/);
});
