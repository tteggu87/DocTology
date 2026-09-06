// Rendering-contract tests without a browser or third-party DOM dependency.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.join(__dirname, '../../dashboard');

function context({fetchImpl,setTimeoutImpl} = {}) {
  const elements = new Map();
  const element = name => {
    if (!elements.has(name)) {
      const classes = new Set();
      elements.set(name, {
        innerHTML:'', textContent:'', hidden:false, disabled:false, value:'', open:false,
        classList:{toggle(value,on){if(on===undefined? !classes.has(value):on)classes.add(value);else classes.delete(value);},add(value){classes.add(value);},remove(value){classes.delete(value);},contains(value){return classes.has(value);}},
        addEventListener(){}, setAttribute(){}, removeAttribute(){}, focus(){}, showModal(){this.open=true;}, close(){this.open=false;},
        querySelector:selector=>element(`${name} ${selector}`), querySelectorAll:()=>[]
      });
    }
    return elements.get(name);
  };
  const storage = new Map();
  const localStorage = {getItem:key=>storage.has(key)?storage.get(key):null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
  const document = {querySelector:element,querySelectorAll:()=>[],addEventListener(){},body:element('body'),hidden:false};
  const fetch = fetchImpl || (async()=>({ok:true,json:async()=>({})}));
  const testSetTimeout=setTimeoutImpl||((callback,delay)=>{const timer=setTimeout(callback,delay);timer.unref?.();return timer;});
  const sandbox = vm.createContext({document,console,setTimeout:testSetTimeout,clearTimeout,URL,fetch,localStorage,confirm:()=>true});
  const html = fs.readFileSync(path.join(assets,'index.html'),'utf8');
  const scripts = [...html.matchAll(/<script src=\"([^\"]+)\" defer><\/script>/g)].map(match=>match[1]).filter(src=>src !== '/boot.js');
  const source = scripts.map(src=>fs.readFileSync(path.join(assets,src.replace(/^\//,'')),'utf8')).join('\n');
  for (const src of scripts) vm.runInContext(fs.readFileSync(path.join(assets,src.replace(/^\//,'')),'utf8'), sandbox, {filename:src});
  const example = fs.readFileSync(path.join(assets,'example.json'),'utf8');
  vm.runInContext(`state = ${example}; state.root='/example'; state.mode='wiki'; state.piAvailable=true; selected=state.sources[3].id; loadHistoryForRoot(state.root);`,sandbox);
  return {sandbox,element,storage,source,run:code=>vm.runInContext(code,sandbox)};
}

function setAnswer(c, {answer='근거가 있는 답변 [1]',references=[],candidates=[],exploration=null}={}) {
  c.run(`conversations=[{id:'c1',title:'대화',createdAt:1,updatedAt:1,messages:[{role:'user',content:'질문'},{role:'assistant',content:${JSON.stringify(answer)},references:${JSON.stringify(references)},candidates:${JSON.stringify(candidates)},exploration:${JSON.stringify(exploration)}}],job:null,error:''}];activeConversationId='c1';selectedAnswerIndex=1;`);
}
function graphCoordinates(html) {
  return Object.fromEntries([...html.matchAll(/data-page="([^"]+)"[^>]*transform="translate\(([-\d.]+) ([-\d.]+)\)"/g)].map(match=>[match[1],[Number(match[2]),Number(match[3])]]));
}

test('three-column layout remains visible at the 1152 CSS-pixel zoom viewport',()=>{
  const css=fs.readFileSync(path.join(assets,'style.css'),'utf8');
  assert.match(css,/@media \(min-width: 1000px\) and \(max-width: 1250px\)/);
  assert.match(css,/\.studio-shell \{ margin-left: 190px; margin-right: 300px; \}/);
  assert.match(css,/@media \(max-width: 999px\)/);
  assert.doesNotMatch(css,/@media \(max-width: 1180px\)/);
});

test('wiki work leaves new conversations and chat submission enabled, with live-read notice',()=>{
  const c=context();
  c.run(`state.demo=false; state.chatAvailable=true;`);
  for (const status of ['starting','running','stopping','external']) {
    c.run(`state.job={status:${JSON.stringify(status)}}; renderChat();`);
    assert.equal(c.element('#chat-submit').disabled,false);
    assert.equal(c.element('.new-conversation').disabled,false);
    assert.equal(c.element('#chat-work-notice').hidden,false);
    assert.equal(c.run('newConversation()'),true);
  }
  c.run(`state.job={status:'finished'}; renderChat();`);
  assert.equal(c.element('#chat-work-notice').hidden,true);
  c.run(`state.job={status:'running'}; state.demo=true; renderChat();`);
  assert.equal(c.element('#chat-work-notice').hidden,true);
});

test('many reference cards retain content height instead of collapsing into empty rows',()=>{
  const css=fs.readFileSync(path.join(assets,'style.css'),'utf8');
  assert.match(css,/\.answer-references\s*\{[^}]*grid-auto-rows:\s*max-content/);
});

test('reader header stays outside its independently scrolling body',()=>{
  const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  const css=fs.readFileSync(path.join(assets,'style.css'),'utf8');
  assert.match(html,/aria-label="문서 닫기"[\s\S]*?<div id="document-scroll"[\s\S]*?<article id="document-body"/);
  assert.match(css,/\.document-dialog\s*\{[^}]*overflow:\s*hidden/);
  assert.match(css,/\.document-scroll\s*\{[^}]*min-height:\s*0;[^}]*overflow:\s*auto/);
  assert.match(css,/\.document-dialog\[open\]\s*\{[^}]*display:\s*flex/);
  assert.match(html,/aria-label="대화 빠른 이동"/);
});

test('chat jump controls reflect overflow and the current scroll boundary',()=>{
  const c=context(),area=c.element('#chat-messages');
  Object.assign(area,{scrollHeight:1000,clientHeight:400,scrollTop:0});
  c.run('updateChatScrollControls()');
  assert.equal(c.element('#chat-scroll-controls').hidden,false);
  assert.equal(c.element('#chat-scroll-top').disabled,true);
  assert.equal(c.element('#chat-scroll-bottom').disabled,false);
  area.scrollTop=600; c.run('updateChatScrollControls()');
  assert.equal(c.element('#chat-scroll-top').disabled,false);
  assert.equal(c.element('#chat-scroll-bottom').disabled,true);
  area.scrollHeight=300; c.run('updateChatScrollControls()');
  assert.equal(c.element('#chat-scroll-controls').hidden,true);
});

test('jump actions scroll only the chat and respect reduced motion',()=>{
  const c=context(),calls=[],area=c.element('#chat-messages');
  area.scrollHeight=1800; area.scrollTo=value=>calls.push(value);
  c.run("jumpChat('bottom');jumpChat('top');");
  assert.equal(calls[0].top,1800); assert.equal(calls[1].top,0);
  assert.equal(calls[0].behavior,'smooth');
  c.sandbox.matchMedia=()=>({matches:true}); c.run("jumpChat('bottom');");
  assert.equal(calls[2].behavior,'instant');
});

test('opening another document resets only the reader body scroll position',async()=>{
  const c=context(); c.element('#document-scroll').scrollTop=900;
  c.element('#chat-messages').scrollTop=300;
  await c.run("openPage('wiki/example.md')");
  assert.equal(c.element('#document-scroll').scrollTop,0);
  assert.equal(c.element('#chat-messages').scrollTop,300);
});

test('default surface is chat, including read-only project mode',()=>{
  const c=context();
  assert.equal(c.run('view'),'chat');
  c.run("state.mode='project'; view='chat'; applyView();");
  assert.equal(c.element('#chat-view').hidden,false);
  assert.equal(c.element('#work-view').hidden,true);
  assert.match(fs.readFileSync(path.join(assets,'index.html'),'utf8'),/id="chat-form"/);
});

test('empty chat suggestions are derived from actual graph nodes',()=>{
  const c=context();
  const firstTitle=c.run('state.graph.nodes[0].title');
  const html=c.run('renderEmptyChat()');
  assert.ok(html.includes(firstTitle));
  assert.match(html,/data-suggestion=/);
  assert.doesNotMatch(html,/PDF를 요약/);
});

test('explicit citations and retrieval candidates remain visibly distinct',()=>{
  const c=context();
  const cited={id:c.run('state.graph.nodes[0].id'),title:'실제 인용',number:1,excerpt:'인용 구절',rawSources:[]};
  const candidate={id:c.run('state.graph.nodes[1].id'),title:'검색 후보',number:2,excerpt:'',rawSources:[]};
  setAnswer(c,{references:[cited],candidates:[candidate]});
  c.run('renderChat();renderReferences();');
  assert.match(c.element('#chat-messages').innerHTML,/class="citation-link"/);
  assert.match(c.element('#chat-messages').innerHTML,/검색 후보 1개/);
  assert.match(c.element('#chat-messages').innerHTML,/답변의 인용과 다릅니다/);
  assert.match(c.element('#answer-references').innerHTML,/실제 인용/);
  assert.doesNotMatch(c.element('#answer-references').innerHTML,/검색 후보/);
});

test('exploration shows escaped actual tool activity and read documents separately from citations',()=>{
  const c=context();
  const cited={id:'wiki/quoted.md',title:'명시 인용',number:1,rawSources:[]};
  const read={id:'wiki/read.md',title:'읽은 <img src=x>',number:2,rawSources:[]};
  const exploration={calls:3,readCount:1,events:[{tool:'wiki_search',query:'<script>query</script>',count:2,status:'ok'},{tool:'wiki_read',path:'wiki/read.md',count:42,status:'ok'}],limits:{calls:8,reads:3},exhausted:false};
  setAnswer(c,{references:[cited],candidates:[read],exploration});
  c.run('renderChat();renderReferences();');
  const html=c.element('#chat-messages').innerHTML;
  assert.match(html,/도구 활동 · 호출 3회 · 문서 읽기 1개/);
  assert.match(html,/42자/);
  assert.match(html,/wiki_search/);
  assert.match(html,/&lt;script&gt;query&lt;\/script&gt;/);
  assert.doesNotMatch(html,/<script>/);
  assert.match(html,/읽은 문서 1개/);
  assert.match(html,/wiki_read로 실제 읽은 문서/);
  assert.match(c.element('#answer-references').innerHTML,/명시 인용/);
  assert.doesNotMatch(c.element('#answer-references').innerHTML,/읽은/);
});

test('native tool disclosure clicks do not rerender their enclosing answer',()=>{
  const c=context();
  c.run("var focusCalls=0;focusAnswer=()=>{focusCalls+=1;};handleClick({target:{closest:selector=>selector==='summary'?{}:{dataset:{answerIndex:'1'},hasAttribute:()=>false}}});");
  assert.equal(c.run('focusCalls'),0);
});

test('open tool disclosures survive refresh only within their owning conversation',()=>{
  const c=context(); setAnswer(c); c.run('renderChat()');
  const oldDetail={open:true,closest:()=>({dataset:{answerIndex:'1'}}),classList:{contains:()=>false}};
  const newDetail={...oldDetail,open:false};
  c.element('#chat-messages').querySelectorAll=selector=>selector==='details[open]'?[oldDetail]:selector==='details'?[newDetail]:[];
  c.run('renderChat()'); assert.equal(newDetail.open,true);
  newDetail.open=false;
  c.run("conversations.push({id:'other',title:'다른 대화',messages:[]});activeConversationId='other';renderChat();");
  assert.equal(newDetail.open,false);
});

test('numeric markers become links only when an explicit matching reference exists',()=>{
  const c=context();
  const references=[{id:'wiki/known.md',title:'Known',number:1,rawSources:[]}];
  const rendered=c.run(`renderAnswerMarkdown('확인 [1] 미확인 [2]',${JSON.stringify(references)})`);
  assert.match(rendered,/data-citation-number="1"/);
  assert.doesNotMatch(rendered,/data-citation-number="2"/);
  assert.match(rendered,/미확인 \[2\]/);
});

test('reference cards expose actual linked raw sources',()=>{
  const c=context();
  setAnswer(c,{references:[{id:'wiki/topic.md',title:'주제',number:1,excerpt:'근거',rawSources:[{id:'raw/source.md',title:'원문 A'}]}]});
  c.run('renderReferences();');
  const html=c.element('#answer-references').innerHTML;
  assert.match(html,/연결된 원문/);
  assert.match(html,/data-page="raw\/source.md"/);
  assert.match(html,/원문 A/);
});

test('the full graph keeps cited nodes when the honest display limit truncates',()=>{
  const c=context();
  c.run(`state.graph.nodes=Array.from({length:90},(_,i)=>({id:'wiki/n'+i+'.md',title:'Node '+i}));state.graph.edges=[];`);
  setAnswer(c,{references:[{id:'wiki/n89.md',title:'Node 89',number:1,rawSources:[]}]});
  c.run('renderKnowledgeGraph();');
  assert.match(c.element('#knowledge-graph').innerHTML,/data-page="wiki\/n89.md"/);
  assert.equal((c.element('#knowledge-graph').innerHTML.match(/class="knowledge-node/g)||[]).length,80);
  assert.match(c.element('#knowledge-graph-scope').textContent,/전체 90개 중 80개 표시/);
});

test('knowledge graph layout stays stable across citation focus when all nodes fit',()=>{
  const c=context();
  c.run(`state.graph={nodes:[{id:'c',title:'Same PDF'},{id:'a',title:'Same PDF'},{id:'d',title:'Other'},{id:'b',title:'Same PDF'}],edges:[{source:'a',target:'b'},{source:'b',target:'c'},{source:'c',target:'d'}]};`);
  setAnswer(c,{references:[{id:'a',title:'Same PDF',number:3,rawSources:[]}]});
  c.run('renderKnowledgeGraph()');
  const first=graphCoordinates(c.element('#knowledge-graph').innerHTML);
  setAnswer(c,{references:[{id:'c',title:'Same PDF',number:7,rawSources:[]}]});
  c.run('renderKnowledgeGraph()');
  const secondHTML=c.element('#knowledge-graph').innerHTML,second=graphCoordinates(secondHTML);
  assert.deepEqual(second,first);
  assert.match(secondHTML,/\[7\] Same PDF/);
});

test('knowledge graph normalizes the force layout into safe usable bounds',()=>{
  const c=context();
  c.run(`state.graph={nodes:[{id:'a',title:'A'},{id:'b',title:'B'},{id:'c',title:'C'},{id:'d',title:'D'}],edges:[{source:'a',target:'b'},{source:'b',target:'c'},{source:'c',target:'d'}]};conversations=[];activeConversationId='';selectedAnswerIndex=-1;renderKnowledgeGraph();`);
  const values=Object.values(graphCoordinates(c.element('#knowledge-graph').innerHTML));
  const xs=values.map(value=>value[0]),ys=values.map(value=>value[1]);
  assert.ok(Math.min(...xs)>=32-1e-6&&Math.max(...xs)<=308+1e-6);
  assert.ok(Math.min(...ys)>=30-1e-6&&Math.max(...ys)<=270+1e-6);
  assert.ok(Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))>=230);
});

test('citation path highlighting uses only existing state.graph edges',()=>{
  const c=context();
  c.run(`state.graph={nodes:[{id:'a',title:'A'},{id:'b',title:'B'},{id:'c',title:'C'}],edges:[{source:'a',target:'b'},{source:'b',target:'c'}]};`);
  setAnswer(c,{references:[{id:'a',title:'A',number:1,rawSources:[]},{id:'c',title:'C',number:2,rawSources:[]}]});
  c.run('renderKnowledgeGraph();');
  const html=c.element('#knowledge-graph').innerHTML;
  assert.equal((html.match(/<line /g)||[]).length,2);
  assert.equal((html.match(/citation-path/g)||[]).length,2);
});

test('past assistant turn selection focuses its own references',()=>{
  const c=context();
  c.run(`conversations=[{id:'c',title:'t',messages:[{role:'assistant',content:'첫 답',references:[{id:'first',title:'첫 근거',number:1,rawSources:[]}]},{role:'assistant',content:'둘째 답',references:[{id:'second',title:'둘째 근거',number:1,rawSources:[]}]}]}];activeConversationId='c';selectedAnswerIndex=1;focusAnswer(0);renderReferences();`);
  assert.match(c.element('#answer-references').innerHTML,/첫 근거/);
  assert.doesNotMatch(c.element('#answer-references').innerHTML,/둘째 근거/);
});

test('model, source, candidate, and document HTML are escaped',()=>{
  const c=context();
  c.run("state.sources[0].title='<img src=x onerror=alert(1)>';renderBoard();");
  assert.doesNotMatch(c.element('#board').innerHTML,/<img/);
  const answer=c.run(`renderAnswerMarkdown('<script>alert(1)</script> **safe**',[{id:'x',title:'x',number:1,rawSources:[]}])`);
  assert.doesNotMatch(answer,/<script/);
  assert.match(answer,/<strong>safe<\/strong>/);
  const documentHTML=c.run("renderMarkdown('[Private](../../secrets.md) <iframe src=x>', 'wiki/index.md')");
  assert.doesNotMatch(documentHTML,/<iframe/);
  assert.doesNotMatch(documentHTML,/href=/);
});

test('relative Markdown links navigate only to known project or raw documents',()=>{
  const c=context();
  c.run("state.mode='project';state.graph.nodes.push({id:'docs/CURRENT_STATE.md',title:'Current state'});documentLinks.add('raw/source.md');");
  const rendered=c.run("renderMarkdown('[Current](../../docs/CURRENT_STATE.md) [Raw](../../raw/source.md) [Private](../../secrets.md) [External](https://example.com)', 'wiki/_meta/index.md')");
  assert.match(rendered,/data-page="docs\/CURRENT_STATE.md"/);
  assert.match(rendered,/data-page="raw\/source.md"/);
  assert.doesNotMatch(rendered,/data-page=".*secrets/);
  assert.doesNotMatch(rendered,/href=/);
});

test('document reads bind expectedRoot and ignore a stale response after root changes',async()=>{
  let resolveResponse,seenUrl='';
  const c=context({fetchImpl:async url=>{seenUrl=url;return new Promise(resolve=>{resolveResponse=resolve;});}});
  const pending=c.run("state.demo=false;state.root='/root-a';openPage('wiki/page.md')");
  c.run("state.root='/root-b'");
  resolveResponse({ok:true,json:async()=>({path:'wiki/page.md',title:'Stale title',text:'STALE BODY',rawSources:[],links:[]})});
  await pending;
  assert.match(seenUrl,/expectedRoot=%2Froot-a/);
  assert.doesNotMatch(c.element('#document-body').textContent+c.element('#document-body').innerHTML,/STALE BODY/);
  assert.notEqual(c.element('#document-title').textContent,'Stale title');
});

test('workspace root change resets and closes the document reader',()=>{
  const c=context();
  c.run("documentLinks.add('raw/old.md');documentRequest=7;var reader=$('#document-dialog');reader.open=true;$('#document-title').textContent='Old';$('#document-body').textContent='Old body';resetDocumentReader();");
  assert.equal(c.run('documentRequest'),8);
  assert.equal(c.run('documentLinks.size'),0);
  assert.equal(c.element('#document-dialog').open,false);
  assert.equal(c.element('#document-title').textContent,'문서');
  assert.equal(c.element('#document-body').textContent,'');
  assert.match(c.source,/if \(rootChanged\) \{\s*resetDocumentReader\(\)/);
});

test('chat history is separated by workspace root',()=>{
  const c=context();
  c.run(`loadHistoryForRoot('/one');ensureConversation().messages.push({role:'user',content:'one only'});saveHistory();loadHistoryForRoot('/two');`);
  assert.equal(c.run('conversations.length'),0);
  c.run("loadHistoryForRoot('/one')");
  assert.equal(c.run("currentConversation().messages[0].content"),'one only');
  assert.notEqual(c.run("storageKey('/one')"),c.run("storageKey('/two')"));
});

test('local persistence bounds messages, evidence snippets, and total serialized bytes',()=>{
  const c=context();
  c.run(`var rawMany=Array.from({length:40},(_,i)=>({id:'raw/'+i,title:'R'.repeat(800)}));var refMany=Array.from({length:40},(_,i)=>({id:'wiki/'+i,title:'T'.repeat(800),number:i+1,excerpt:'E'.repeat(5000),rawSources:rawMany}));conversations=[{id:'large',title:'Large',updatedAt:2,messages:Array.from({length:70},(_,i)=>({role:i%2?'assistant':'user',content:'한'.repeat(25000),references:i===69?refMany:[],candidates:i===69?refMany:[]}))},{id:'older',title:'Older',updatedAt:1,messages:Array.from({length:20},()=>({role:'user',content:'x'.repeat(25000)}))}];activeConversationId='large';var localPayload=buildHistoryPayload();var localData=JSON.parse(localPayload.json);`);
  assert.ok(c.run('localPayload.bytes')<=c.run('LOCAL_STORAGE_BYTES_LIMIT'));
  assert.ok(c.run('localData.conversations.length')<=c.run('LOCAL_CONVERSATION_LIMIT'));
  assert.ok(c.run('localData.conversations.every(item=>item.messages.length<=LOCAL_MESSAGE_LIMIT)'));
  assert.ok(c.run('localData.conversations.every(item=>item.messages.every(message=>message.content.length<=LOCAL_MESSAGE_TEXT_LIMIT&&message.references.length<=LOCAL_EVIDENCE_LIMIT&&message.candidates.length<=LOCAL_EVIDENCE_LIMIT))'));
  assert.ok(c.run('localData.conversations.every(item=>item.messages.every(message=>message.references.every(reference=>reference.excerpt.length<=LOCAL_EXCERPT_LIMIT&&reference.rawSources.length<=LOCAL_EVIDENCE_LIMIT)))'));
  assert.equal(c.run('localPayload.truncated'),true);
});

test('exploration persistence bounds trace count and strings without raw event data',()=>{
  const c=context();
  c.run(`conversations=[{id:'c',title:'t',messages:[{role:'assistant',content:'답',references:[],candidates:[],exploration:{calls:99999999,readCount:99999999,events:Array.from({length:40},(_,i)=>({tool:i%2?'wiki_read':'wiki_search',path:'p'.repeat(3000),query:'q'.repeat(3000),status:'s'.repeat(300),count:99999999,raw:'do not persist'})),limits:{calls:99999999,reads:99999999},exhausted:true}}]}];activeConversationId='c';var normalized=normalizeConversation(conversations[0]);`);
  assert.equal(c.run('normalized.messages[0].exploration.events.length'),24);
  assert.ok(c.run('normalized.messages[0].exploration.events.every(event=>(event.path||\'\').length<=2000&&(event.query||\'\').length<=2000&&(event.status||\'\').length<=120&&!Object.hasOwn(event,\'raw\'))'));
  assert.equal(c.run('normalized.messages[0].exploration.calls'),1000000);
  assert.equal(c.run('normalized.messages[0].exploration.limits.reads'),1000000);
});

test('exhausted exploration warns without claiming completion or inventing an answer',()=>{
  const c=context();
  setAnswer(c,{answer:'',exploration:{calls:8,readCount:2,events:[{tool:'wiki_read',path:'wiki/a.md'}],exhausted:true}});
  c.run('renderChat();');
  const html=c.element('#chat-messages').innerHTML;
  assert.match(html,/탐색 한도에 도달했습니다/);
  assert.match(html,/완료를 뜻하지 않으며/);
  assert.doesNotMatch(html,/완료했습니다/);
});

test('legacy messages retain search candidate wording when exploration is absent',()=>{
  const c=context();
  setAnswer(c,{candidates:[{id:'wiki/old.md',title:'기존 후보',number:1,rawSources:[]}]});
  c.run('renderChat();');
  assert.match(c.element('#chat-messages').innerHTML,/검색 후보 1개/);
  assert.doesNotMatch(c.element('#chat-messages').innerHTML,/읽은 문서 1개/);
});

test('exploration preserves invalidated reads and labels a clipped tool trace',()=>{
  const c=context();
  const exploration={calls:30,readCount:4,invalidatedReadCount:2,events:Array.from({length:24},()=>({tool:'wiki_read',path:'wiki/a.md'})),exhausted:false};
  const html=c.run(`renderExploration(normalizeExploration(${JSON.stringify(exploration)}))`);
  assert.match(html,/문서 읽기 4개/);
  assert.match(html,/최근 24개 도구 호출/);
  assert.match(html,/읽은 근거 2개가 무효화/);
  assert.match(html,/현재 읽기 수 4개는 유지/);
});

test('localStorage quota failure is reported in both toast and persistent status',()=>{
  const c=context({setTimeoutImpl:()=>1});
  c.sandbox.localStorage.setItem=()=>{throw new Error('quota');};
  assert.equal(c.run("ensureConversation().messages.push({role:'user',content:'keep in memory'});saveHistory()"),false);
  c.run('renderChat()');
  assert.equal(c.element('#toast').hidden,false);
  assert.match(c.element('#toast').textContent,/저장하지 못했습니다/);
  assert.match(c.element('#chat-status').textContent,/저장하지 못했습니다/);
  assert.equal(c.run("currentConversation().messages.at(-1).content"),'keep in memory');
});

test('history payload stays within the live backend limits',()=>{
  const c=context();
  c.run(`var bounded=chatHistoryPayload(Array.from({length:20},(_,i)=>({role:i%2?'assistant':'user',content:'x'.repeat(7000)})));`);
  assert.ok(c.run('bounded.length')<=12);
  assert.ok(c.run('bounded.every(item=>item.content.length<=6000)'));
  assert.ok(c.run('bounded.reduce((sum,item)=>sum+item.content.length,0)')<=24000);
});

test('retry submits the failed last question without duplicating it',async()=>{
  const calls=[];
  const c=context({fetchImpl:async(url,options)=>{calls.push({url,options});return {ok:false,json:async()=>({error:'offline'})};}});
  await c.run("submitChat('한 번만 남겨줘')");
  assert.equal(c.run('currentConversation().messages.length'),1);
  await c.run("submitChat('한 번만 남겨줘',{reuseLast:true})");
  assert.equal(c.run('currentConversation().messages.length'),1);
  assert.equal(calls.length,2);
});

test('running chat renders escaped partial answer, provisional citations, candidates, and elapsed seconds',()=>{
  const c=context();
  c.run("ensureConversation().messages.push({role:'user',content:'질문'});activeChatJob={id:'j',conversationId:activeConversationId,root:'/example',startedAt:Date.now()-4200,answer:'부분 <script>x</script> [1]',references:[{id:'wiki/partial.md',title:'부분 근거',number:1,rawSources:[]}],candidates:[{id:'candidate',title:'후보',number:1,rawSources:[]}]};renderChat();");
  const html=c.element('#chat-messages').innerHTML;
  assert.equal(c.element('#chat-stop').hidden,false);
  assert.match(html,/부분 &lt;script&gt;x&lt;\/script&gt;/);
  assert.doesNotMatch(html,/<script>/);
  assert.match(html,/data-reference-id="wiki\/partial.md"/);
  assert.match(html,/4초/);
  assert.match(html,/완료 전 바뀔 수 있습니다/);
  assert.match(html,/아직 답변의 인용이 아닙니다/);
  assert.match(c.element('#chat-status').textContent,/4초 · 응답 생성 중/);
});

test('polling applies the running response before the terminal answer',async()=>{
  let c,call=0,sawPartial=false;
  const reference={id:'wiki/live.md',title:'실시간 근거',number:1,rawSources:[]};
  c=context({setTimeoutImpl:callback=>{callback();return 1;},fetchImpl:async()=>{
    call+=1;
    if(call===1)return {ok:true,json:async()=>({id:'j',root:'/example',status:'running',answer:'폴링 부분 [1]',references:[reference],candidates:[reference],startedAt:Date.now()/1000-2})};
    sawPartial=/폴링 부분/.test(c.element('#chat-messages').innerHTML)&&/data-reference-id="wiki\/live.md"/.test(c.element('#chat-messages').innerHTML);
    return {ok:true,json:async()=>({id:'j',root:'/example',status:'finished',answer:'최종 [1]',references:[reference],candidates:[reference],startedAt:Date.now()/1000-2,endedAt:Date.now()/1000})};
  }});
  c.run("var live=ensureConversation();live.messages.push({role:'user',content:'질문'});activeChatJob={id:'j',conversationId:live.id,root:'/example',status:'running',startedAt:Date.now(),answer:'',references:[],candidates:[]};");
  await c.run("pollChat('j','/example',live.id)");
  assert.equal(sawPartial,true);
  assert.equal(c.run("currentConversation().messages.at(-1).content"),'최종 [1]');
});

test('a transient poll failure keeps the chat handle and reaches a later running and finished status',async()=>{
  let call=0;
  const reference={id:'wiki/live.md',title:'근거',number:1,rawSources:[]};
  const c=context({setTimeoutImpl:callback=>{callback();return 1;},fetchImpl:async()=>{
    call+=1;
    if(call===1)return {ok:false,status:503,json:async()=>({error:'temporary network'})};
    if(call===2)return {ok:true,json:async()=>({id:'j',root:'/example',status:'running',answer:'이어진 초안',references:[reference],candidates:[],startedAt:Date.now()/1000})};
    return {ok:true,json:async()=>({id:'j',root:'/example',status:'finished',answer:'완료 답변',references:[reference],candidates:[],startedAt:Date.now()/1000,endedAt:Date.now()/1000})};
  }});
  c.run("var live=ensureConversation();live.messages.push({role:'user',content:'질문'});activeChatJob={id:'j',conversationId:live.id,root:'/example',status:'running',startedAt:Date.now(),answer:'',references:[],candidates:[],exploration:null};");
  await c.run("pollChat('j','/example',live.id)");
  assert.equal(call,3);
  assert.equal(c.run('activeChatJob'),null);
  assert.equal(c.run("currentConversation().messages.at(-1).content"),'완료 답변');
});

test('repeated poll failures preserve the handle and manual stop retrieves its terminal state',async()=>{
  let stopBody;
  const c=context({setTimeoutImpl:callback=>{callback();return 1;},fetchImpl:async(_url,options)=>{
    if(options?.method==='POST') { stopBody=JSON.parse(options.body); return {ok:true,json:async()=>({ok:true})}; }
    if(stopBody)return {ok:true,json:async()=>({id:'j-live',root:'/example',status:'stopped'})};
    return {ok:false,status:503,json:async()=>({error:'offline'})};
  }});
  c.run("var live=ensureConversation();live.messages.push({role:'user',content:'질문'});activeChatJob={id:'j-live',conversationId:live.id,root:'/example',status:'running',startedAt:Date.now(),answer:'부분',references:[],candidates:[],exploration:null};conversationForFailures=live;");
  await c.run("pollChat('j-live','/example',conversationForFailures.id)");
  assert.equal(c.run('activeChatJob.id'),'j-live');
  assert.equal(c.run('currentConversation().job.id'),'j-live');
  assert.match(c.run('currentConversation().error'),/연결 다시 확인/);
  c.run('renderChat()');
  assert.match(c.element('#chat-messages').innerHTML,/연결 다시 확인/);
  assert.equal(c.element('#chat-stop').hidden,false);
  await c.run('stopChat()');
  assert.equal(stopBody.id,'j-live');
  assert.equal(c.run('activeChatJob'),null);
  assert.equal(c.run('currentConversation().job'),null);
  assert.match(c.run('currentConversation().error'),/중단했습니다/);
});

test('a confirmed missing chat status preserves the received partial before clearing the handle',async()=>{
  const c=context({fetchImpl:async()=>({ok:false,status:404,json:async()=>({error:'chat job missing'})})});
  c.run("var live=ensureConversation();live.messages.push({role:'user',content:'질문'});activeChatJob={id:'missing',conversationId:live.id,root:'/example',status:'running',startedAt:Date.now(),answer:'마지막 초안',references:[],candidates:[],exploration:null};");
  await c.run("pollChat('missing','/example',live.id)");
  assert.equal(c.run('activeChatJob'),null);
  assert.equal(c.run('currentConversation().job'),null);
  assert.equal(c.run('currentConversation().messages.at(-1).partial'),true);
  assert.equal(c.run('currentConversation().messages.at(-1).content'),'마지막 초안');
});

test('citation opening rejects a current document whose hash differs from the cited snapshot',async()=>{
  const citedHash='a'.repeat(64),currentHash='b'.repeat(64);
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({path:'wiki/a.md',title:'A',text:'CURRENT',contentHash:currentHash,rawSources:[],links:[]})})});
  c.run(`state.demo=false;state.root='/example';openReferenceById('wiki/a.md',[{id:'wiki/a.md',title:'A',number:1,contentHash:'${citedHash}',readRanges:[{offset:0,end:4}],rawSources:[]}]);`);
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(c.element('#document-kind').textContent,/MISMATCH/);
  assert.match(c.element('#document-body').textContent,/현재 문서를 오래된 인용의 근거로 표시하지 않았습니다/);
  assert.doesNotMatch(c.element('#document-body').innerHTML,/CURRENT/);
});

test('citation hash metadata is bounded and a matching snapshot renders normally',async()=>{
  const hash='c'.repeat(64);
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({path:'wiki/a.md',title:'A',text:'CURRENT',contentHash:hash,rawSources:[],links:[]})})});
  c.run(`var referenceMetadata=normalizeReference({id:'wiki/a.md',contentHash:'${hash}',readRanges:[{offset:0,end:3},{offset:-1,end:2},...Array.from({length:80},(_,i)=>({offset:i,end:i+1}))]},0);state.demo=false;state.root='/example';openReferenceById('wiki/a.md',[referenceMetadata]);`);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(c.run('referenceMetadata.contentHash'),hash);
  assert.ok(c.run('referenceMetadata.readRanges.length')<=64);
  assert.match(c.element('#document-body').innerHTML,/CURRENT/);
});

test('loading, cancel, and error controls are explicit before a partial answer arrives',()=>{
  const c=context();
  c.run("ensureConversation().messages.push({role:'user',content:'질문'});activeChatJob={id:'j',conversationId:activeConversationId,root:'/example',startedAt:Date.now(),answer:'',references:[],candidates:[]};renderChat();");
  assert.equal(c.element('#chat-stop').hidden,false);
  assert.match(c.element('#chat-messages').innerHTML,/위키에서 근거를 찾고 있습니다/);
  c.run("activeChatJob=null;currentConversation().error='실패 내용';renderChat();");
  assert.match(c.element('#chat-messages').innerHTML,/실패 내용/);
  assert.match(c.element('#chat-messages').innerHTML,/다시 시도/);
});

test('graph zoom changes the SVG viewport transform, not only its label',()=>{
  const c=context();
  c.run('zoom=1.4;renderGraph();');
  assert.match(c.element('#graph-canvas').innerHTML,/class="graph-viewport"/);
  assert.match(c.element('#graph-canvas').innerHTML,/scale\(1.4\)/);
  assert.equal(c.element('#zoom-label').textContent,'140%');
});

test('empty board copy distinguishes writable wiki and read-only project modes',()=>{
  const c=context();
  c.run("state.sources=[];state.mode='wiki';renderBoard();");
  assert.match(c.element('#board').innerHTML,/첫 번째 원문을 추가해 보세요/);
  assert.doesNotMatch(c.element('#board').innerHTML,/프로젝트 모드에서는/);
  c.run("state.mode='project';renderBoard();");
  assert.match(c.element('#board').innerHTML,/프로젝트는 읽기 전용입니다/);
});

test('new, clear, and history switching cannot orphan an active chat job',()=>{
  const c=context();
  c.run(`conversations=[{id:'one',title:'one',messages:[]},{id:'two',title:'two',messages:[]}];activeConversationId='one';activeChatJob={id:'starting',conversationId:'one',root:'/example',startedAt:Date.now()};renderChat();`);
  assert.equal(c.element('.new-conversation').disabled,true);
  assert.equal(c.element('[data-action="clear-history"]').disabled,true);
  assert.equal(c.run('newConversation()'),false);
  assert.equal(c.run('clearHistory()'),false);
  assert.equal(c.run("selectConversation('two')"),false);
  assert.equal(c.run('conversations.length'),2);
  assert.equal(c.run('activeConversationId'),'one');
  assert.equal(c.run('activeChatJob.id'),'starting');
});

test('citation click focuses the owning historical answer before resolving its reference',()=>{
  const c=context();
  c.run(`conversations=[{id:'c',title:'t',messages:[{role:'assistant',content:'첫 답 [1]',references:[{id:'wiki/first.md',title:'첫 근거',number:1,rawSources:[]}]},{role:'assistant',content:'둘째 답 [1]',references:[{id:'wiki/second.md',title:'둘째 근거',number:1,rawSources:[]}]}]}];activeConversationId='c';selectedAnswerIndex=1;var citationTarget={dataset:{referenceId:'wiki/first.md'},hasAttribute:()=>false};var citationOwner={dataset:{answerIndex:'0'}};var clickOrigin={closest:selector=>selector==='button,a,[data-page],[data-answer-index]'?citationTarget:selector==='[data-answer-index]'?citationOwner:null};handleClick({target:clickOrigin});`);
  assert.equal(c.run('selectedAnswerIndex'),0);
  assert.equal(c.element('#document-path').textContent,'wiki/first.md');
});

test('kanban progress and validation controls remain available as secondary work',()=>{
  const c=context();
  c.run('renderBoard();renderGraph();renderDetail();');
  assert.match(c.element('#board').innerHTML,/column-card selected/);
  assert.match(c.element('#graph-canvas').innerHTML,/graph-edge related/);
  c.run("selected=state.sources[6].id;currentSource().stage='blocked';currentSource().run.blockers=['STRUCTURAL_VALIDATION_FAILED'];renderDetail();");
  assert.match(c.element('#detail-panel').innerHTML,/구조 검증<small>실패/);
  assert.doesNotMatch(c.element('#detail-panel').innerHTML,/구조 검증<small>확인됨/);
});

test('missing and stale receipts do not manufacture percentage progress',()=>{
  const c=context();
  c.run('selected=state.sources[0].id;renderDetail();');
  assert.match(c.element('#detail-panel').innerHTML,/범위 확인 전/);
  c.run('selected=state.sources[3].id;currentSource().coverage.valid=false;renderDetail();');
  assert.match(c.element('#detail-panel').innerHTML,/집계를 표시하지 않습니다/);
});

test('project work view shows real inventory without simulated execution',()=>{
  const c=context();
  c.run("state.mode='project';state.demo=false;state.root='/project';state.sources=[];selectedPage=state.graph.nodes[0].id;renderProjectStats();renderProjectDetail();renderLibrary();renderRun();");
  assert.match(c.element('#stats').innerHTML,/프로젝트 위키/);
  assert.doesNotMatch(c.element('#stats').innerHTML,/검증 완료/);
  assert.match(c.element('#detail-panel').innerHTML,/이 문서를 참조하는 문서/);
  assert.match(c.element('#run-strip').innerHTML,/PROJECT WIKI · READ ONLY/);
});

test('optional backend default model is displayed without configuring an account',()=>{
  const c=context();
  c.run("state.chatDefaultModel='openai-codex/gpt-5.5';render();");
  assert.equal(c.element('#chat-model').placeholder,'GPT-5.5 · Pi 기본');
  assert.equal(c.element('#pi-status').textContent,'기본 · GPT-5.5');
});

test('composer disclosure explains model data transfer and source verification',()=>{
  const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  assert.match(html,/질문과 문서 발췌가 선택한 모델에 전달됩니다\. 인용은 원문에서 확인하세요\./);
});

test('no model call occurs merely by loading the frontend module',()=>{
  let calls=0;
  context({fetchImpl:async()=>{calls+=1;return {ok:true,json:async()=>({})};}});
  assert.equal(calls,0);
});


test('folder watch is manually off by default and auto-run requires a separate checkbox',()=>{
  const c=context();
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:false,autoRun:false,sourcePath:'',queue:[],counts:{pending:0,running:0,completed:0,needsAttention:0}};renderAutomation();");
  const html=c.element('#automation-panel').innerHTML;
  assert.match(html,/꺼짐 · 기본값/);
  assert.match(html,/name="enabled"/);
  assert.match(html,/name="autoRun"/);
  assert.doesNotMatch(html,/name="autoRun" checked/);
  assert.match(html,/선택한 모델을 사용해 위키 파일을 변경할 수 있음/);
  assert.match(html,/기존 파일도 처음 한 번 감지/);
  assert.match(html,/\/vault\/raw/);
});

test('rendering the watch surface never configures a watcher or invokes a model',()=>{
  const calls=[];
  const c=context({fetchImpl:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({})};}});
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};renderAutomation();view='watch';applyView();");
  assert.equal(calls.length,0);
  assert.equal(c.element('#automation-panel').hidden,false);
});

test('project mode visibly disables chat capture and folder watch with reasons',()=>{
  const c=context();
  setAnswer(c);
  c.run("state.demo=false;state.mode='project';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};renderChat();renderAutomation();");
  assert.match(c.element('#chat-messages').innerHTML,/answer-save-button[^>]*disabled/);
  assert.match(c.element('#chat-messages').innerHTML,/프로젝트는 읽기 전용/);
  assert.match(c.element('#automation-panel').innerHTML,/프로젝트는 읽기 전용/);
  assert.match(c.element('#automation-panel').innerHTML,/type="submit" disabled/);
});

test('chat save selection enforces server bounds and refuses truncated local history',()=>{
  const c=context();
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';currentConversation().messages[1].truncated=true;");
  assert.match(c.run("chatSaveReason(1,'answer')"),/잘린 로컬 메시지/);
  assert.equal(c.run("openChatSave(1,'answer')"),false);
  c.run("currentConversation().messages[1].truncated=false;currentConversation().historyTruncated=true;");
  assert.match(c.run("chatSaveReason(1,'conversation')"),/전체 대화를 저장할 수 없습니다/);
  c.run("currentConversation().historyTruncated=false;currentConversation().messages=Array.from({length:41},(_,i)=>({role:i%2?'assistant':'user',content:'x'}));");
  assert.match(c.run("chatSaveReason(1,'conversation')"),/40개 메시지/);
  c.run("currentConversation().messages=[{role:'user',content:'x'.repeat(49000)},{role:'assistant',content:'y'.repeat(49000),references:[{id:'wiki/a.md',title:'A',number:1,excerpt:'e'.repeat(3000),rawSources:[]}]}];");
  assert.match(c.run("chatSaveReason(1,'conversation')"),/100,000자/);
});

test('preview requests are root-bound and send only the selected question and answer',async()=>{
  let seenBody;
  const c=context({fetchImpl:async(_url,options)=>{seenBody=JSON.parse(options.body);return {ok:true,json:async()=>({previewId:'p1',root:'/vault',title:'제목',sourcePath:'raw/inbox/chat.md',markdown:'# 제목\n\n본문',warnings:['검증 전 대화'],expiresAt:99})};}});
  setAnswer(c,{references:[{id:'wiki/a.md',title:'A',number:1,rawSources:[]}]});
  c.run("state.demo=false;state.root='/vault';historyRoot='/vault';saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';$('input[name=\"scope\"]:checked').value='answer';");
  await c.run("requestChatSavePreview({scope:'answer',title:'제목',answerIndex:1})");
  assert.equal(seenBody.expectedRoot,'/vault');
  assert.equal(seenBody.messages.length,2);
  assert.deepEqual(seenBody.messages.map(message=>message.role),['user','assistant']);
  assert.equal(seenBody.messages[1].references[0].id,'wiki/a.md');
  assert.equal('rawSources' in seenBody.messages[1].references[0],false);
  assert.equal(c.run('savePreview.previewId'),'p1');
  assert.equal(c.element('#chat-save-preview').textContent,'# 제목\n\n본문');
});

test('root changes invalidate pending preview responses and close the dialog',async()=>{
  let resolveResponse;
  const c=context({fetchImpl:async()=>new Promise(resolve=>{resolveResponse=resolve;})});
  setAnswer(c);
  c.run("state.demo=false;state.root='/one';historyRoot='/one';saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';");
  const pending=c.run("requestChatSavePreview({scope:'answer',title:'제목',answerIndex:1})");
  c.run("state.root='/two';invalidateSavePreview({close:true});");
  resolveResponse({ok:true,json:async()=>({previewId:'stale',root:'/one',title:'제목',sourcePath:'raw/stale.md',markdown:'STALE',warnings:[]})});
  await pending;
  assert.equal(c.run('savePreview'),null);
  assert.equal(c.element('#chat-save-dialog').open,false);
  assert.doesNotMatch(c.element('#chat-save-preview').textContent,/STALE/);
});

test('editing title or scope invalidates an immutable preview before commit',()=>{
  const c=context({setTimeoutImpl:()=>1});
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};savePreview={previewId:'p',root:'/vault',title:'Old',scope:'answer'};markSavePreviewStale();");
  assert.equal(c.run('savePreview'),null);
  assert.equal(c.element('#chat-save-submit').disabled,true);
  assert.match(c.element('#chat-save-preview').textContent,/다시 만들고 있습니다/);
});

test('saved chat labels source preservation separately from gate completion',()=>{
  const c=context();
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[{id:'q1',source:'raw/inbox/chat.md',title:'대화',status:'pending',change:'conversation',createdAt:1,updatedAt:1,targets:[]}],counts:{}};currentConversation().messages[1].save={itemId:'q1',sourcePath:'raw/inbox/chat.md',root:'/vault',scope:'answer'};renderChat();");
  let html=c.element('#chat-messages').innerHTML;
  assert.match(html,/원문 보존 · 위키 정리 대기/);
  assert.doesNotMatch(html,/기존 게이트 통과/);
  assert.match(html,/data-action="show-watch"/);
  assert.match(html,/data-page="raw\/inbox\/chat.md"/);
  c.run("state.automation.queue[0].status='completed';state.automation.queue[0].targets=[{id:'wiki/topic.md',title:'완성 문서'}];renderChat();");
  html=c.element('#chat-messages').innerHTML;
  assert.match(html,/위키 정리 완료 · 기존 게이트 통과/);
  assert.match(html,/data-page="wiki\/topic.md"/);
});

test('watch queue shows honest statuses, elapsed records, reasons, targets, and explicit row actions',()=>{
  const c=context();
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:true,autoRun:false,sourcePath:'/vault/raw',queue:[{id:'p',source:'raw/a.md',title:'<img src=x>',status:'pending',change:'added',reason:'검토 & 필요',createdAt:10,updatedAt:20,targets:[]},{id:'a',source:'raw/b.md',title:'B',status:'needs_attention',change:'modified',createdAt:10,updatedAt:20,targets:[]},{id:'c',source:'raw/c.md',title:'C',status:'completed',change:'conversation',createdAt:10,updatedAt:20,endedAt:20,targets:[{id:'wiki/c.md',title:'C wiki'}]},{id:'d',source:'raw/d.md',title:'D',status:'deleted',change:'modified',createdAt:10,updatedAt:20,targets:[]}],counts:{pending:1,running:0,completed:1,needsAttention:1}};renderAutomation();");
  const html=c.element('#automation-panel').innerHTML;
  assert.doesNotMatch(html,/<img/);
  assert.match(html,/검토 &amp; 필요/);
  assert.match(html,/data-watch-run="p"[^>]*>실행/);
  assert.match(html,/data-watch-run="a"[^>]*>재시도/);
  assert.match(html,/data-watch-ignore="p"/);
  assert.match(html,/삭제됨/);
  assert.match(html,/실제 반영 대상/);
  assert.match(html,/data-page="wiki\/c.md"/);
  assert.doesNotMatch(html,/예상 완료|드래그해서/);
});

test('chat capture controls and uncertainty warning remain visible and escaped',()=>{
  const c=context();
  setAnswer(c,{answer:'<script>bad()</script>'});
  c.run("state.demo=false;state.root='/vault';renderChat();");
  const html=c.element('#chat-messages').innerHTML;
  assert.match(html,/위키에 저장/);
  assert.match(html,/대화 전체 저장/);
  assert.match(html,/사실 검증이나 위키 완료를 뜻하지 않습니다/);
  assert.doesNotMatch(html,/<script>/);
  const index=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  assert.match(index,/위키로 정리 시작/);
  assert.match(index,/서버가 만든 Markdown/);
  assert.match(index,/name="scope" value="answer"/);
  assert.match(index,/name="scope" value="conversation"/);
});


test('chat save commit sends only the immutable preview id and records the queue link locally',async()=>{
  let seenBody;
  const c=context({fetchImpl:async(_url,options)=>{seenBody=JSON.parse(options.body);return {ok:true,json:async()=>({sourcePath:'raw/inbox/conversations/chat.md',item:{id:'queue-1',source:'raw/inbox/conversations/chat.md',title:'Saved',origin:'conversation',status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]},alreadySaved:false})};}});
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';historyRoot='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};savePreview={previewId:'preview_abcdefghijklmnop',root:'/vault',title:'제목',scope:'answer',answerIndex:1,sourcePath:'raw/inbox/conversations/chat.md'};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';$('input[name=\"scope\"]:checked').value='answer';");
  await c.run('commitChatSave()');
  assert.deepEqual(seenBody,{expectedRoot:'/vault',previewId:'preview_abcdefghijklmnop'});
  assert.equal(c.run("currentConversation().messages[1].save.itemId"),'queue-1');
  assert.match(c.element('#chat-messages').innerHTML,/원문 보존 · 위키 정리 대기/);
});


test('automation heartbeat timestamps do not force full rerenders but queue changes still do',()=>{
  const c=context();
  assert.equal(c.run("stateSignature({root:'/v',checkedAt:1,automation:{checkedAt:2,queue:[]}})===stateSignature({root:'/v',checkedAt:9,automation:{checkedAt:10,queue:[]}})"),true);
  assert.equal(c.run("stateSignature({root:'/v',automation:{checkedAt:2,queue:[]}})===stateSignature({root:'/v',automation:{checkedAt:3,queue:[{id:'new'}]}})"),false);
});

test('dirty root-bound watch settings survive queue rerenders without hiding new rows',()=>{
  const c=context();
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:false,autoRun:false,sourcePath:'/vault/raw',queue:[],counts:{}};watchDraft={root:'/vault',dirty:true,enabled:true,autoRun:true,sourcePath:'/external/notes',includeExisting:true};state.automation.queue=[{id:'new',source:'raw/new.md',title:'새 원문',status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]}];renderAutomation();");
  let html=c.element('#automation-panel').innerHTML;
  assert.match(html,/value="\/external\/notes"/);
  assert.match(html,/name="enabled" checked/);
  assert.match(html,/name="autoRun" checked/);
  assert.match(html,/name="includeExisting" checked/);
  assert.match(html,/입력 변경 적용 전/);
  assert.match(html,/새 원문/);
  c.run("state.root='/other';renderAutomation();");
  html=c.element('#automation-panel').innerHTML;
  assert.doesNotMatch(html,/\/external\/notes/);
});

test('chat save commit uses captured preview and context if the dialog closes during the request',async()=>{
  let resolveResponse;
  const c=context({fetchImpl:async()=>new Promise(resolve=>{resolveResponse=resolve;})});
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';historyRoot='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};savePreview={previewId:'preview-captured',root:'/vault',title:'제목',scope:'answer',answerIndex:1,sourcePath:'raw/chat.md',warnings:[]};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';$('input[name=\"scope\"]:checked').value='answer';");
  const pending=c.run('commitChatSave()');
  assert.equal(c.element('#chat-save-title').disabled,true);
  c.run("invalidateSavePreview({close:true});saveContext={conversationId:'wrong'};");
  resolveResponse({ok:true,json:async()=>({sourcePath:'raw/chat.md',item:{id:'queue-captured',source:'raw/chat.md',title:'Saved',origin:'conversation',status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]},alreadySaved:false})});
  await pending;
  assert.equal(c.run("conversations.find(value=>value.id==='c1').messages[1].save.itemId"),'queue-captured');
  assert.equal(c.element('#chat-save-title').disabled,false);
});

test('recoverable 409 keeps the exact preview for queue handoff retry without inventing a job',async()=>{
  let resolveResponse;
  const c=context({fetchImpl:async()=>new Promise(resolve=>{resolveResponse=resolve;})});
  setAnswer(c);
  c.run("state.demo=false;state.root='/vault';historyRoot='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};savePreview={previewId:'same-preview',root:'/vault',title:'제목',scope:'answer',answerIndex:1,sourcePath:'raw/chat-saved.md',markdown:'EXACT MARKDOWN',warnings:[]};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';$('#chat-save-preview').textContent='EXACT MARKDOWN';$('input[name=\"scope\"]:checked').value='answer';");
  const pending=c.run("commitChatSave().catch(error=>{handleChatSaveError(error);})");
  c.run("invalidateSavePreview({close:true})");
  resolveResponse({ok:false,status:409,json:async()=>({recoverable:true,sourcePath:'raw/chat-saved.md',queueHandoff:false,error:'대화 원문은 저장됐지만 위키 작업 대기열 등록에 실패했습니다.'})});
  await pending;
  assert.equal(c.run('savePreview.previewId'),'same-preview');
  assert.equal(c.element('#chat-save-dialog').open,true);
  assert.equal(c.element('#chat-save-preview').textContent,'EXACT MARKDOWN');
  assert.match(c.element('#chat-save-meta').textContent,/원문 저장됨 · 대기열 등록 재시도 필요/);
  assert.equal(c.element('#chat-save-submit').textContent,'대기열 등록 다시 시도');
  assert.equal(c.element('#chat-save-submit').disabled,false);
  assert.equal(c.run('state.automation.queue.length'),0);
  assert.equal(c.run('currentConversation().messages[1].save'),undefined);
});

test('a root change during durable save reports the old-root result without linking it to the new workspace',async()=>{
  let resolveResponse;
  const c=context({fetchImpl:async()=>new Promise(resolve=>{resolveResponse=resolve;})});
  setAnswer(c);
  c.run("state.demo=false;state.root='/old';historyRoot='/old';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};saveContext={scope:'answer',answerIndex:1,conversationId:'c1'};savePreview={previewId:'old-preview',root:'/old',title:'제목',scope:'answer',answerIndex:1,sourcePath:'raw/old.md',warnings:[]};$('#chat-save-dialog').open=true;$('#chat-save-title').value='제목';$('input[name=\"scope\"]:checked').value='answer';");
  const pending=c.run('commitChatSave()');
  c.run("state.root='/new';invalidateSavePreview({close:true});");
  resolveResponse({ok:true,json:async()=>({sourcePath:'raw/old.md',item:{id:'old-queue',source:'raw/old.md',status:'pending',targets:[]}})});
  await pending;
  assert.equal(c.run('currentConversation().messages[1].save'),undefined);
  assert.match(c.element('#toast').textContent,/이전 워크스페이스에 원문이 저장되고 작업 대기열에 등록/);
});

test('watch-off disclosure distinguishes paused detection from existing and explicit work',()=>{
  const c=context();
  c.run("state.demo=false;state.root='/vault';state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};renderAutomation();");
  const html=c.element('#automation-panel').innerHTML;
  assert.match(html,/감시 OFF는 새 변경 감지와 자동 실행 시작을 멈춥니다/);
  assert.match(html,/현재 실행, 명시적 수동 실행, 대화 원문 저장은 취소되지 않습니다/);
});


test('watch queue paginates 105 actionable rows with honest all-status counts',()=>{
  const c=context();
  c.run("state.demo=false;state.root='/vault';watchDraft={root:'/vault',dirty:true,enabled:true,autoRun:false,sourcePath:'/external',includeExisting:false};state.automation={available:true,enabled:true,autoRun:false,sourcePath:'/vault/raw',queue:Array.from({length:100},(_,i)=>({id:'p'+i,source:'raw/'+i+'.md',title:'Pending '+i,status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]})),queuePage:{offset:0,limit:100,total:105},counts:{pending:105,running:0,completed:0,needsAttention:0}};renderAutomation();");
  let html=c.element('#automation-panel').innerHTML;
  assert.match(html,/대기 105/);
  assert.match(html,/1–100 \/ 전체 105개/);
  assert.match(html,/data-action="queue-previous" disabled/);
  assert.match(html,/data-action="queue-next" >다음/);
  assert.match(html,/value="\/external"/);
  c.run("state.automation.queue=Array.from({length:5},(_,i)=>({id:'p'+(100+i),source:'raw/'+(100+i)+'.md',title:'Pending '+(100+i),status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]}));state.automation.queuePage={offset:100,limit:100,total:105};renderAutomation();");
  html=c.element('#automation-panel').innerHTML;
  assert.match(html,/101–105 \/ 전체 105개/);
  assert.match(html,/data-action="queue-previous" >이전/);
  assert.match(html,/data-action="queue-next" disabled/);
  assert.match(html,/value="\/external"/);
});

test('queue page requests use offsets, adopt the server page, and keep offset zero backward-compatible',async()=>{
  const base=JSON.parse(fs.readFileSync(path.join(assets,'example.json'),'utf8'));
  base.root='/example';base.mode='wiki';base.demo=false;base.automation={available:true,enabled:false,autoRun:false,sourcePath:'/example/raw',queue:Array.from({length:5},(_,i)=>({id:'p'+(100+i),source:'raw/'+i+'.md',title:'P'+i,status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]})),queuePage:{offset:100,limit:100,total:105},counts:{pending:105,running:0,completed:0,needsAttention:0}};
  const first=JSON.parse(JSON.stringify(base));first.automation.queue=Array.from({length:100},(_,i)=>({id:'p'+i,source:'raw/'+i+'.md',title:'P'+i,status:'pending',change:'added',createdAt:1,updatedAt:1,targets:[]}));first.automation.queuePage={offset:0,limit:100,total:105};
  const urls=[];
  const c=context({fetchImpl:async url=>{urls.push(url);const payload=url.includes('queueOffset=100')?base:first;return {ok:true,json:async()=>JSON.parse(JSON.stringify(payload))};}});
  c.run("watchQueueOffset=100;watchDraft={root:'/example',dirty:true,enabled:true,autoRun:false,sourcePath:'/draft',includeExisting:false};");
  await c.run('refresh(true)');
  assert.equal(urls.filter(url=>url.startsWith('/api/state'))[0],'/api/state?queueOffset=100');
  assert.equal(c.run('watchQueueOffset'),100);
  assert.match(c.element('#automation-panel').innerHTML,/101–105/);
  await c.run('moveWatchQueuePage(-1)');
  assert.equal(urls.filter(url=>url.startsWith('/api/state'))[1],'/api/state');
  assert.equal(c.run('watchQueueOffset'),0);
  assert.match(c.element('#automation-panel').innerHTML,/value="\/draft"/);
});

test('workspace root changes reset a nonzero queue offset and refetch the first page',async()=>{
  const next=JSON.parse(fs.readFileSync(path.join(assets,'example.json'),'utf8'));
  next.root='/new-root';next.mode='wiki';next.demo=false;next.automation={available:true,enabled:false,autoRun:false,sourcePath:'/new-root/raw',queue:[],queuePage:{offset:0,limit:100,total:0},counts:{pending:0,running:0,completed:0,needsAttention:0}};
  const stalePage=JSON.parse(JSON.stringify(next));stalePage.automation.queuePage={offset:100,limit:100,total:205};
  const urls=[];
  const c=context({fetchImpl:async url=>{urls.push(url);const payload=url.includes('queueOffset=100')?stalePage:next;return {ok:true,json:async()=>JSON.parse(JSON.stringify(payload))};}});
  c.run("watchQueueOffset=100;watchDraft={root:'/example',dirty:true,enabled:true,autoRun:true,sourcePath:'/old-draft',includeExisting:true};");
  await c.run('refresh(true)');
  assert.deepEqual(urls.filter(url=>url.startsWith('/api/state')),['/api/state?queueOffset=100','/api/state']);
  assert.equal(c.run('watchQueueOffset'),0);
  assert.equal(c.run('watchDraft'),null);
  assert.equal(c.run('historyRoot'),'/new-root');
});

test('missing parallel worker metadata preserves canonical source stages',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'running',parallel:{phase:'preparing',parallelism:3,workers:[{source:state.sources[0].id}]}}; state.sources[0].stage='done'; renderBoard();");
  assert.match(c.element('#board').innerHTML,/검증 완료/);
  assert.doesNotMatch(c.element('#board').innerHTML,/worker-badge/);
});

test('prepared worker is visibly awaiting integration, never counted as canonical completion',()=>{
  const c=context();
  c.run("state.demo=false; state.sources[0].stage='writing'; state.job={id:'j1',status:'running',parallel:{phase:'prepared',parallelism:3,workers:[{source:state.sources[0].id,status:'prepared',attempt:1,readCount:2}]}}; renderStats(); renderRun(); renderBoard(); renderDetail();");
  assert.match(c.element('#board').innerHTML,/초안 준비됨 · 통합 대기/);
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 완료 · 통합 대기/);
  assert.match(c.element('#stats').innerHTML,/검증 완료/);
  assert.doesNotMatch(c.element('#stats').innerHTML,/1<small>\/ /);
});

test('parallel worker badges map real states and run strip reports worker concurrency',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'running',parallel:{phase:'preparing',parallelism:3,workers:[{source:state.sources[0].id,status:'pending'},{source:state.sources[1].id,status:'reading'},{source:state.sources[2].id,status:'drafting'}]}}; renderRun(); renderBoard();");
  const html=c.element('#board').innerHTML;
  assert.match(html,/대기열/); assert.match(html,/읽는 중/); assert.match(html,/초안 작성 중/);
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 0\/3 · 동시 실행 2\/3/);
});

test('worker stop and retry send isolated root and job payloads and ignore stale responses',async()=>{
  const calls=[]; const c=context({fetchImpl:async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({})};}});
  c.run("state.root='/one';state.job={id:'j1',status:'running'};");
  await c.run("controlParallelWorker('raw/a.md','stop')");
  await c.run("controlParallelWorker('raw/b.md','retry')");
  assert.deepEqual(calls,[['/api/batch-worker-stop',{expectedRoot:'/one',jobId:'j1',source:'raw/a.md'}],['/api/batch-worker-retry',{expectedRoot:'/one',jobId:'j1',source:'raw/b.md'}]]);
  const stale=context({fetchImpl:async()=>{stale.run("state.root='/two';state.job={id:'j2'}");return {ok:true,json:async()=>({})};}});
  stale.run("state.root='/one';state.job={id:'j1',status:'running'};"); await stale.run("controlParallelWorker('raw/a.md','stop')");
  assert.equal(stale.run('state.root'),'/two');
});

test('task start only forwards requested parallelism for multiple sources and chat remains independent',()=>{
  const source=fs.readFileSync(path.join(assets,'app.js'),'utf8'); const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  assert.match(html,/name="parallelism"/); assert.match(html,/<option value="3" selected>/);
  assert.match(source,/parallelPreparationAvailable\(\)&&sources\.length>1\?\{parallelism:Number\(form\.get\('parallelism'\)\)\|\|3\}:\{\}/);
  const c=context(); c.run("state.job={id:'j1',status:'running',parallel:{phase:'preparing',workers:[]}}; renderChat();");
  assert.equal(c.element('#chat-submit').disabled,false);
});

test('parallel preparation form is advertised only by an explicitly capable server',()=>{
  const capable=context();
  capable.run("state.demo=false; state.parallelPreparationAvailable=true; state.job=null; openTask('start');");
  assert.equal(capable.element('#parallelism-field').hidden,false);
  capable.run("taskMode='steer'; openTask('steer');");
  assert.equal(capable.element('#parallelism-field').hidden,true);
  const legacy=context();
  legacy.run("state.demo=false; delete state.parallelPreparationAvailable; state.job=null; openTask('start');");
  assert.equal(legacy.element('#parallelism-field').hidden,true);
  assert.equal(legacy.run('parallelPreparationAvailable()'),false);
});

test('parallelism is sent only when the server explicitly supports preparation',()=>{
  const c=context();
  c.run("state.demo=false; state.parallelPreparationAvailable=true; taskMode='start';");
  assert.equal(c.run("parallelPreparationAvailable()&&2>1 ? ({parallelism:Number('4')||3}).parallelism : undefined"),4);
  c.run("delete state.parallelPreparationAvailable;");
  assert.equal(c.run("parallelPreparationAvailable()&&2>1 ? ({parallelism:Number('4')||3}).parallelism : undefined"),undefined);
  const source=fs.readFileSync(path.join(assets,'app.js'),'utf8');
  assert.match(source,/parallelPreparationAvailable\(\)&&sources\.length>1/);
});


test('pending workers do not inflate prepared or concurrent execution counts',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'running',parallel:{phase:'planning',parallelism:3,workers:[{source:state.sources[0].id,status:'pending'},{source:state.sources[1].id,status:'pending'}]}}; renderRun();");
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 0\/2 · 동시 실행 0\/3/);
});

test('reading and drafting workers count as concurrent execution only',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'running',parallel:{phase:'preparing',parallelism:3,workers:[{source:state.sources[0].id,status:'reading'},{source:state.sources[1].id,status:'drafting'},{source:state.sources[2].id,status:'pending'}]}}; renderRun(); renderBoard();");
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 0\/3 · 동시 실행 2\/3/);
  assert.match(c.element('#board').innerHTML,/위키 상태: /);
  assert.doesNotMatch(c.element('#board').innerHTML,/초안 작성 중 초안 작성 중/);
  assert.doesNotMatch(c.element('#board').innerHTML,/인증 읽기/);
});

test('prepared workers count as drafts but never canonical gate completion',()=>{
  const c=context();
  c.run("state.demo=false; state.sources[0].stage='writing'; state.sources[1].stage='reading'; state.job={id:'j1',status:'running',parallel:{phase:'prepared',parallelism:3,workers:[{source:state.sources[0].id,status:'prepared'},{source:state.sources[1].id,status:'prepared'}]}}; renderRun(); renderBoard();");
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 2\/2 · 동시 실행 0\/3/);
  assert.match(c.element('#board').innerHTML,/초안 준비됨 · 통합 대기/);
  assert.doesNotMatch(c.element('#board').innerHTML,/기존 검증 완료/);
});

test('integration resume is shown only for a stopped eligible coordinator',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'finished',parallel:{canResumeIntegration:true,workers:[]}}; renderRun();");
  assert.match(c.element('#run-strip').innerHTML,/data-action="resume-integration"/);
  c.run("state.job.status='running'; renderRun();");
  assert.doesNotMatch(c.element('#run-strip').innerHTML,/resume-integration/);
  c.run("state.job.status='finished'; delete state.job.parallel.canResumeIntegration; renderRun();");
  assert.doesNotMatch(c.element('#run-strip').innerHTML,/resume-integration/);
  c.run("state.job.parallel.canResumeIntegration=false; renderRun();");
  assert.doesNotMatch(c.element('#run-strip').innerHTML,/resume-integration/);
});

test('integration resume posts only root and job and ignores a stale workspace response',async()=>{
  const calls=[]; const c=context({fetchImpl:async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({})};}});
  c.run("state.root='/one'; state.job={id:'j1',status:'finished',parallel:{canResumeIntegration:true}};");
  await c.run('resumeParallelIntegration()');
  assert.deepEqual(calls[0],['/api/batch-resume',{expectedRoot:'/one',jobId:'j1'}]);
  const stale=context({fetchImpl:async()=>{stale.run("state.root='/two';state.job={id:'j2'}");return {ok:true,json:async()=>({})};}});
  stale.run("state.root='/one'; state.job={id:'j1',status:'finished',parallel:{canResumeIntegration:true}};");
  await stale.run('resumeParallelIntegration()');
  assert.equal(stale.run('state.root'),'/two');
});

test('cleanup-pending workers remain processing and expose retry only when allowed',()=>{
  const c=context();
  c.run("state.demo=false; state.job={id:'j1',status:'finished',parallel:{workers:[{source:state.sources[0].id,status:'stopped',cleanupPending:true,canRetry:false}]}}; selected=state.sources[0].id; renderDetail();");
  assert.match(c.element('#detail-panel').innerHTML,/중단 처리 중/);
  assert.doesNotMatch(c.element('#detail-panel').innerHTML,/data-worker-retry/);
  c.run("state.job.parallel.workers[0].canRetry=true; renderDetail();");
  assert.match(c.element('#detail-panel').innerHTML,/data-worker-retry/);
});

test('a verified source projects stale prepared draft copy without awaiting integration',()=>{
  const c=context();
  c.run("state.demo=false; state.sources[0].stage='done'; state.job={id:'j1',status:'finished',sources:[state.sources[0].id],parallel:{phase:'prepared',parallelism:3,workers:[{source:state.sources[0].id,status:'prepared'}]}}; selected=state.sources[0].id; renderRun(); renderBoard(); renderDetail();");
  assert.match(c.element('#board').innerHTML,/초안 준비됨/);
  assert.match(c.element('#board').innerHTML,/검증 완료/);
  assert.doesNotMatch(c.element('#board').innerHTML,/초안 준비됨 · 통합 대기/);
  assert.doesNotMatch(c.element('#detail-panel').innerHTML,/통합 대기/);
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 기록됨 · 현재 원문 검증 완료/);
  assert.doesNotMatch(c.element('#run-strip').innerHTML,/통합 대기/);
});

test('an unverified requested source retains prepared awaiting-integration copy',()=>{
  const c=context();
  c.run("state.demo=false; state.sources[0].stage='writing'; state.job={id:'j1',status:'finished',sources:[state.sources[0].id],parallel:{phase:'prepared',parallelism:3,workers:[{source:state.sources[0].id,status:'prepared'}]}}; selected=state.sources[0].id; renderRun(); renderBoard(); renderDetail();");
  assert.match(c.element('#board').innerHTML,/초안 준비됨 · 통합 대기/);
  assert.match(c.element('#detail-panel').innerHTML,/초안 준비됨 · 통합 대기/);
  assert.match(c.element('#run-strip').innerHTML,/초안 준비 완료 · 통합 대기/);
});


test('folder picker posts an empty authenticated chooser payload and fills only the connection path',async()=>{
  const requests=[];
  const c=context({fetchImpl:async(url,options)=>{
    requests.push({url,options});
    return {ok:true,json:async()=>({root:'/picked/wiki',cancelled:false})};
  }});
  c.element('#connect-dialog').open=true;
  c.element('#connect-root').value='/manual/wiki';
  await c.run('chooseFolder()');
  assert.equal(requests.at(-1).url,'/api/choose-folder');
  assert.equal(requests.at(-1).options.method,'POST');
  assert.equal(requests.at(-1).options.body,'{}');
  assert.equal(c.element('#connect-root').value,'/picked/wiki');
  assert.equal(requests.filter(request=>request.url==='/api/connect').length,0);
  assert.equal(c.element('#connect-dialog').open,true);
});

test('folder picker cancellation preserves the manually entered path',async()=>{
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({cancelled:true})})});
  c.element('#connect-dialog').open=true;
  c.element('#connect-root').value='/keep/this';
  await c.run('chooseFolder()');
  assert.equal(c.element('#connect-root').value,'/keep/this');
  assert.equal(c.element('.form-error').textContent,'');
  assert.equal(c.element('#choose-folder').disabled,false);
});

test('native picker failure opens the in-app browser rather than only requiring a manual path',async()=>{
  const requests=[];
  const c=context({fetchImpl:async(url,options)=>{
    requests.push([url,JSON.parse(options.body)]);
    if(url==='/api/choose-folder')throw new Error('OS picker unavailable');
    return {ok:true,json:async()=>({path:'/home',parent:'/',directories:[],shortcuts:[],truncated:false})};
  }});
  c.element('#connect-dialog').open=true;
  c.element('#connect-root').value='/manual/wiki';
  await c.run('chooseFolder()');
  assert.equal(c.element('#connect-root').value,'/manual/wiki');
  assert.equal(c.element('#choose-folder').disabled,false);
  assert.equal(c.element('#folder-browser-dialog').open,true);
  assert.deepEqual(requests.at(-1),['/api/browse-folders',{}]);
  assert.match(c.element('#folder-picker-note').textContent,/OS 창 대신 작업실에서 폴더를 선택하세요/);
});

test('late folder picker results are ignored after dialog closure or manual root edits',async()=>{
  let resolveFirst;
  const first=new Promise(resolve=>{resolveFirst=resolve;});
  const c=context({fetchImpl:()=>first});
  c.element('#connect-dialog').open=true;
  c.element('#connect-root').value='/original';
  const pending=c.run('chooseFolder()');
  c.element('#connect-dialog').open=false;
  c.run('invalidateFolderPicker()');
  resolveFirst({ok:true,json:async()=>({root:'/stale/closed',cancelled:false})});
  await pending;
  assert.equal(c.element('#connect-root').value,'/original');

  let resolveSecond;
  const second=new Promise(resolve=>{resolveSecond=resolve;});
  c.sandbox.fetch=()=>second;
  c.element('#connect-dialog').open=true;
  const pendingAgain=c.run('chooseFolder()');
  c.element('#connect-root').value='/manual/change';
  c.run('invalidateFolderPicker()');
  resolveSecond({ok:true,json:async()=>({root:'/stale/changed',cancelled:false})});
  await pendingAgain;
  assert.equal(c.element('#connect-root').value,'/manual/change');
});

test('connection dialog exposes both native and in-app folder actions',()=>{
  const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  const css=fs.readFileSync(path.join(assets,'style.css'),'utf8');
  assert.match(html,/<button id="choose-folder"[^>]*data-action="choose-folder"[^>]*>.*폴더 선택…/);
  assert.match(html,/<button id="browse-folders"[^>]*data-action="browse-folders"[^>]*>작업실에서 폴더 찾기/);
  assert.match(html,/id="folder-browser-dialog"/);
  assert.match(html,/선택한 폴더 <span class="muted">\(직접 입력 가능\)<\/span>/);
  assert.match(css,/\.folder-browser-list\s*\{[^}]*max-height/);
});

test('folder picker preserves significant spaces in native paths',async()=>{
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({root:'/tmp/한글 folder ',cancelled:false})})});
  c.run("openDialog('#connect-dialog')");
  await c.run('chooseFolder()');
  assert.equal(c.element('#connect-root').value,'/tmp/한글 folder ');
});

test('folder picker drops results after connected workspace changes and unlocks form',async()=>{
  let resolve;
  const c=context({fetchImpl:()=>new Promise(done=>{resolve=done;})});
  c.run("openDialog('#connect-dialog')");
  c.element('#connect-root').value='/unchanged';
  const pending=c.run('chooseFolder()');
  c.run("state.root='/different-workspace'");
  resolve({ok:true,json:async()=>({root:'/chosen',cancelled:false})});
  await pending;
  assert.equal(c.element('#connect-root').value,'/unchanged');
  assert.equal(c.run('folderPickerPending'),false);
});


test('in-app browser posts browse payloads and navigates directories without connecting',async()=>{
  const requests=[];
  const responses=[
    {path:'/home',parent:'/',directories:[{name:'Projects',path:'/home/Projects'}],shortcuts:[{name:'Home',path:'/home'}],truncated:false},
    {path:'/home/Projects',parent:'/home',directories:[],shortcuts:[],truncated:false}
  ];
  const c=context({fetchImpl:async(url,options)=>{requests.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>responses.shift()};}});
  c.element('#connect-dialog').open=true;
  c.run('openFolderBrowser()');
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(requests[0],['/api/browse-folders',{}]);
  assert.match(c.element('#folder-browser-list').innerHTML,/Projects/);
  await c.run("browseFolders('/home/Projects')");
  assert.deepEqual(requests[1],['/api/browse-folders',{path:'/home/Projects'}]);
  assert.equal(c.element('#folder-browser-path').textContent,'/home/Projects');
  assert.equal(requests.some(([url])=>url==='/api/connect'),false);
});

test('in-app browser escapes directory names and attributes',async()=>{
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({path:'/home',parent:null,directories:[{name:'<img src=x onerror=1>',path:'\" onfocus=alert(1)'}],shortcuts:[{name:'<b>Home</b>',path:'/home'}],truncated:false})})});
  c.element('#connect-dialog').open=true;
  c.run('openFolderBrowser()');
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(c.element('#folder-browser-list').innerHTML,/&lt;img src=x onerror=1&gt;/);
  assert.match(c.element('#folder-browser-list').innerHTML,/&quot; onfocus=alert\(1\)/);
  assert.doesNotMatch(c.element('#folder-browser-list').innerHTML,/<img/);
  assert.match(c.element('#folder-browser-shortcuts').innerHTML,/&lt;b&gt;Home&lt;\/b&gt;/);
});

test('in-app selection fills the connect root and closes only the nested browser',async()=>{
  let connectCalls=0;
  const c=context({fetchImpl:async(url)=>{if(url==='/api/connect')connectCalls+=1;return {ok:true,json:async()=>({path:'/home/wiki',parent:'/home',directories:[],shortcuts:[],truncated:false})};}});
  c.element('#connect-dialog').open=true;
  c.element('#connect-root').value='/manual';
  c.run('openFolderBrowser()');
  await new Promise(resolve=>setImmediate(resolve));
  c.run('selectFolderBrowser()');
  assert.equal(c.element('#connect-root').value,'/home/wiki');
  assert.equal(c.element('#connect-dialog').open,true);
  assert.equal(c.element('#folder-browser-dialog').open,false);
  assert.equal(connectCalls,0);
});

test('closing the nested browser drops a stale directory response and returns to the connection form',async()=>{
  let resolve;
  const c=context({fetchImpl:()=>new Promise(done=>{resolve=done;})});
  c.element('#connect-dialog').open=true;
  c.run('openFolderBrowser()');
  c.element('#folder-browser-dialog').close();
  c.run('invalidateFolderBrowser()');
  resolve({ok:true,json:async()=>({path:'/stale',parent:null,directories:[{name:'Nope',path:'/stale/nope'}],shortcuts:[],truncated:false})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(c.element('#connect-dialog').open,true);
  assert.doesNotMatch(c.element('#folder-browser-list').innerHTML,/Nope/);
});

test('in-app browser shows a bounded-list notice when the server truncates directories',async()=>{
  const c=context({fetchImpl:async()=>({ok:true,json:async()=>({path:'/home',parent:null,directories:[],shortcuts:[],truncated:true})})});
  c.element('#connect-dialog').open=true;
  c.run('openFolderBrowser()');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(c.element('#folder-browser-truncated').hidden,false);
  assert.match(fs.readFileSync(path.join(assets,'index.html'),'utf8'),/표시 가능한 하위 폴더만/);
});


test('per-answer retrieval usage normalizes strictly and persists full aggregates',()=>{
  const c=context();
  const usage={version:1,basis:'successful_discovery_calls',counts:{grep:2,fts:0,wikilinks:1,vector:0},results:{grep:9,fts:0,wikilinks:3,vector:0},listCalls:4,readCalls:2,unsupported:['fts','vector']};
  c.run(`var rawUsage=${JSON.stringify(usage)};var usageNormalized=normalizeRetrievalUsage(rawUsage);conversations=[{id:'usage',title:'u',messages:[{role:'assistant',content:'답',exploration:{calls:24,readCount:2,events:Array.from({length:24},()=>({tool:'wiki_search',query:'old trace'})),retrievalUsage:rawUsage}}]}];activeConversationId='usage';var usagePayload=JSON.parse(buildHistoryPayload().json);`);
  assert.equal(c.run('JSON.stringify(usageNormalized)'),JSON.stringify(usage));
  assert.equal(c.run('JSON.stringify(usagePayload.conversations[0].messages[0].exploration.retrievalUsage)'),JSON.stringify(usage));
  assert.equal(c.run('usagePayload.conversations[0].messages[0].exploration.calls'),24);
  assert.equal(c.run('usagePayload.conversations[0].messages[0].exploration.events.length'),24);
});

test('per-answer retrieval usage reports absent or malformed contract without fabricated zeroes',()=>{
  const c=context();
  const malformed=[
    {version:2,basis:'successful_discovery_calls',counts:{grep:0,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:[]},
    {version:1,basis:'successful_discovery_calls',counts:{grep:-1,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:[]},
    {version:1,basis:'successful_discovery_calls',counts:{grep:1.5,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:[]}
  ];
  for (const value of malformed) assert.equal(c.run(`normalizeRetrievalUsage(${JSON.stringify(value)})`),null);
  assert.equal(c.run("normalizeRetrievalUsage({version:1,basis:'successful_discovery_calls',counts:{grep:Infinity,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:[]})"),null);
  assert.equal(c.run('normalizeRetrievalUsage(null)'),null);
  setAnswer(c,{exploration:{calls:1,readCount:0,events:[]}}); c.run('renderChat();');
  assert.match(c.element('#chat-messages').innerHTML,/검색 사용량 기록 없음/);
  assert.doesNotMatch(c.element('#chat-messages').innerHTML,/성공한 검색·링크 호출 0회/);
});

test('per-answer retrieval usage shows zero denominator honestly and computes 2:1 shares',()=>{
  const c=context();
  const base={version:1,basis:'successful_discovery_calls',results:{grep:0,fts:0,wikilinks:0,vector:0},listCalls:3,readCalls:4,unsupported:[]};
  const zero={...base,counts:{grep:0,fts:0,wikilinks:0,vector:0}};
  const ratio={...base,counts:{grep:2,fts:0,wikilinks:1,vector:0}};
  const zeroHTML=c.run(`renderRetrievalUsage(normalizeRetrievalUsage(${JSON.stringify(zero)}))`);
  assert.match(zeroHTML,/비율 없음/); assert.doesNotMatch(zeroHTML,/width:0%/);
  const ratioHTML=c.run(`renderRetrievalUsage(normalizeRetrievalUsage(${JSON.stringify(ratio)}))`);
  assert.match(ratioHTML,/grep 방식<\/span><strong>2회<\/strong><small>비율 67%/);
  assert.match(ratioHTML,/위키링크<\/span><strong>1회<\/strong><small>비율 33%/);
  assert.match(ratioHTML,/목록 호출 3회 · 본문 읽기 4회/);
  assert.match(ratioHTML,/목록·본문 읽기·실패 제외; 답변 기여도\/정확도가 아님/);
});

test('per-answer retrieval usage keeps unsupported lanes and optional result detail separate',()=>{
  const c=context();
  const usage={version:1,basis:'successful_discovery_calls',counts:{grep:1,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:['fts','vector']};
  const html=c.run(`renderRetrievalUsage(normalizeRetrievalUsage(${JSON.stringify(usage)}))`);
  assert.match(html,/FTS<\/span><strong>채팅 미연결 · 관측 호출 0회/);
  assert.match(html,/벡터<\/span><strong>채팅 미연결 · 관측 호출 0회/);
  assert.doesNotMatch(html,/검색 결과 수/);
  assert.doesNotMatch(html,/<script>|onerror=/);
});

test('partial answers retain their own retrieval usage summary',()=>{
  const c=context();
  const usage={version:1,basis:'successful_discovery_calls',counts:{grep:1,fts:0,wikilinks:0,vector:0},results:{grep:2,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:1,unsupported:['fts','vector']};
  c.run(`var live=ensureConversation();live.messages.push({role:'user',content:'질문'});activeChatJob={id:'u',conversationId:live.id,root:'/example',status:'running',startedAt:Date.now(),answer:'초안',references:[],candidates:[],exploration:normalizeExploration({calls:1,readCount:1,events:[],retrievalUsage:${JSON.stringify(usage)}})};renderChat();`);
  assert.match(c.element('#chat-messages').innerHTML,/검색 호출 구성/);
  assert.match(c.element('#chat-messages').innerHTML,/검색 결과 수 · 인용 또는 고유 문서 수가 아님/);
});


function retrievalStatusFixture(root='/vault') {
  return {version:1,root,checkedAt:1735689600,sqlite:{configured:true,state:'current',freshness:'stat',pages:7,chunks:11,fts:true,reasons:[]},onnx:{state:'configured',packages:{onnxruntime:true,tokenizers:true,numpy:true},modelConfigured:true,modelPresent:true,tokenizerConfigured:true,tokenizerPresent:true,inferenceVerified:false},vectors:{state:'stored',rows:9},chatMethods:{grep:true,fts:false,wikilinks:true,vector:false}};
}

test('retrieval readiness ignores a stale root response and renders only the current root',async()=>{
  const pending=[];
  const c=context({fetchImpl:async (url,options)=>new Promise(resolve=>pending.push({url,options,resolve}))});
  c.run("state.demo=false;state.root='/a';resetRetrievalStatus('/a');");
  const first=c.run('requestRetrievalStatus(true)');
  c.run("state.root='/b';resetRetrievalStatus('/b');");
  const second=c.run('requestRetrievalStatus(true)');
  assert.equal(pending.length,2);
  pending[0].resolve({ok:true,status:200,json:async()=>retrievalStatusFixture('/a')}); await first;
  assert.equal(c.run('retrievalStatus'),null);
  pending[1].resolve({ok:true,status:200,json:async()=>retrievalStatusFixture('/b')}); await second;
  assert.equal(c.run('retrievalStatus.root'),'/b');
  assert.match(c.element('#retrieval-readiness').innerHTML,/SQLite/);
  assert.doesNotMatch(c.element('#retrieval-readiness').innerHTML,/\/a/);
});

test('retrieval readiness coalesces polling and uses the authenticated root-bound POST contract',async()=>{
  let resolveStatus,calls=[];
  const c=context({fetchImpl:async (url,options)=>{calls.push({url,options});return new Promise(resolve=>{resolveStatus=resolve;});}});
  c.run("token='token';state.demo=false;state.root='/vault';resetRetrievalStatus('/vault');");
  const first=c.run('requestRetrievalStatus(true)'),second=c.run('requestRetrievalStatus(true)');
  assert.strictEqual(first,second); assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/retrieval-status');
  assert.equal(calls[0].options.method,'POST');
  assert.equal(calls[0].options.headers['X-Dashboard-Token'],'token');
  assert.deepEqual(JSON.parse(calls[0].options.body),{expectedRoot:'/vault',force:true});
  resolveStatus({ok:true,status:200,json:async()=>retrievalStatusFixture('/vault')}); await first;
  c.run('requestRetrievalStatus(false)');
  assert.equal(calls.length,1);
});

test('retrieval readiness handles unavailable, unknown, demo, and rootless status without fake readiness',async()=>{
  const c=context({fetchImpl:async()=>({ok:false,status:404,json:async()=>({error:'missing'})})});
  c.run("state.demo=false;state.root='/vault';resetRetrievalStatus('/vault');");
  await c.run('requestRetrievalStatus(true)');
  c.run('renderRetrievalStatus()');
  assert.match(c.element('#retrieval-readiness').innerHTML,/지원 안함/);
  assert.match(c.element('#retrieval-status-updated').textContent,/API/);
  c.run("state.demo=true;state.root='/example';resetRetrievalStatus('/example');renderRetrievalStatus();");
  assert.match(c.element('#retrieval-readiness').innerHTML,/지원 안함/);
  c.run("state.demo=false;state.root='';resetRetrievalStatus('');renderRetrievalStatus();");
  assert.match(c.element('#retrieval-readiness').innerHTML,/확인 불가/);
});

test('retrieval readiness distinguishes configured artifacts from execution or chat readiness',()=>{
  const c=context(),status=retrievalStatusFixture('/vault');
  c.run(`state.demo=false;state.root='/vault';retrievalStatusRoot='/vault';retrievalStatus=normalizeRetrievalStatus(${JSON.stringify(status)},'/vault');renderRetrievalStatus();`);
  const compact=c.element('#retrieval-readiness').innerHTML,detail=c.element('#retrieval-status-body').innerHTML;
  assert.match(compact,/ONNX[\s\S]*설정됨 · 추론 미검증/);
  assert.match(detail,/FTS 사용 가능 · 채팅 미연결/);
  assert.match(detail,/현재 채팅은 문자열\+위키링크; FTS\/벡터 채팅 미연결|추론 미검증/);
  assert.match(detail,/저장 행 수는 품질 또는 준비 완료를 뜻하지 않습니다/);
  assert.doesNotMatch(compact,/활성|준비 완료/);
});

test('retrieval readiness markup stays passive and uses sibling badges beneath the workspace button',()=>{
  const html=fs.readFileSync(path.join(assets,'index.html'),'utf8');
  assert.match(html,/<button class="workspace"[\s\S]*?<\/button>\s*<div id="retrieval-readiness"/);
  assert.match(html,/현재 채팅은 문자열\+위키링크; FTS\/벡터 채팅 미연결/);
  assert.match(html,/data-action="refresh-retrieval-status"/);
  assert.doesNotMatch(html,/rebuild|download|enable/i);
});

test('retrieval counts reject unsafe integers and overflowing totals',()=>{
  const c=context();
  assert.equal(c.run("normalizeRetrievalUsage({version:1,basis:'successful_discovery_calls',counts:{grep:1e308,fts:0,wikilinks:0,vector:0},listCalls:0,readCalls:0,unsupported:[]})"),null);
  assert.equal(c.run("normalizeRetrievalUsage({version:1,basis:'successful_discovery_calls',counts:{grep:Number.MAX_SAFE_INTEGER,fts:0,wikilinks:Number.MAX_SAFE_INTEGER,vector:0},listCalls:0,readCalls:0,unsupported:[]})"),null);
});

test('search percentages award remainder to fractional share, not largest lane',()=>{
  const c=context();
  assert.deepEqual(JSON.parse(c.run("JSON.stringify(retrievalUsageShares({grep:7,fts:2,wikilinks:3,vector:0}))")),{grep:58,fts:17,wikilinks:25,vector:0});
});
