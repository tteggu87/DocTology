'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const icons = {
  book:'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h3z',
  layout:'M3 4h7v7H3z M14 4h7v7h-7z M3 15h7v6H3z M14 15h7v6h-7z',
  network:'M12 9v6 M9 7 5 5 M15 7l4-2 M9 17l-4 2 M15 17l4 2 M9 6h6v4H9z M9 14h6v4H9z M2 2h4v4H2z M18 2h4v4h-4z M2 18h4v4H2z M18 18h4v4h-4z',
  files:'M7 3h8l4 4v14H7z M15 3v5h4 M3 7v14 M10 12h6 M10 16h4',
  activity:'M3 12h4l3-8 4 16 3-8h4', lock:'M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0v4', chevron:'m9 5 6 7-6 7',
  refresh:'M20 7a9 9 0 1 0 1 9 M20 2v6h-6', plus:'M12 5v14 M5 12h14',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',
  search:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0', check:'m5 12 4 4 10-10',
  clock:'M12 7v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0', arrow:'M5 12h14 m-5-5 5 5-5 5',
  'arrow-up':'M12 19V5 m-6 6 6-6 6 6', chat:'M4 5h16v11H9l-5 4z', alert:'m12 3 10 18H2z M12 9v5 M12 17v1'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name] || icons.files}"/></svg>`;
$$('[data-icon]').forEach(element => { element.innerHTML = icon(element.dataset.icon); });

let state = null;
let token = '';
let selected = null;
let selectedPage = null;
let view = 'chat';
let query = '';
let blockedOnly = false;
let graphMode = 'all';
let zoom = 1;
let taskMode = 'start';
let lastRender = '';
let loading = false;
let documentRequest = 0;
let documentLinks = new Set();
let conversations = [];
let activeConversationId = '';
let historyRoot = '';
let selectedAnswerIndex = -1;
let renderedChatOwner = '';
let chatScrollObserver = null;
let activeChatJob = null;
let chatPollGeneration = 0;
let historyStorageNotice = '';
let savePreview = null;
let savePreviewGeneration = 0;
let savePreviewTimer = 0;
let saveContext = null;
let chatSaveCommitting = false;
let chatSaveRecovery = null;
let watchSubmitting = false;
let watchDraft = null;
let watchQueueOffset = 0;
let folderPickerGeneration = 0;
let folderPickerPending = false;
let folderBrowserGeneration = 0;
let folderBrowserPending = false;
let folderBrowserLocation = null;
let folderBrowserContext = null;
let retrievalStatus = null;
let retrievalStatusRoot = '';
let retrievalStatusGeneration = 0;
let retrievalStatusRequest = null;
let retrievalStatusLastRequestedAt = 0;

const GRAPH_LIMIT = 80;
const LOCAL_CONVERSATION_LIMIT = 30;
const LOCAL_MESSAGE_LIMIT = 60;
const LOCAL_MESSAGE_TEXT_LIMIT = 20000;
const LOCAL_EVIDENCE_LIMIT = 24;
const LOCAL_EXCERPT_LIMIT = 2000;
const LOCAL_EXPLORATION_EVENT_LIMIT = 24;
const LOCAL_EXPLORATION_TEXT_LIMIT = 2000;
const LOCAL_STORAGE_BYTES_LIMIT = 500000;
const CHAT_POLL_FAILURE_LIMIT = 3;
const CHAT_POLL_BACKOFF_MS = 650;
const CHAT_SAVE_MESSAGE_LIMIT = 40;
const CHAT_SAVE_CHARS_LIMIT = 100000;
const RETRIEVAL_STATUS_POLL_MS = 30000;
const queueLabels = {pending:'대기',running:'실행 중',completed:'완료',needs_attention:'확인 필요',ignored:'제외됨',deleted:'삭제됨',superseded:'새 변경으로 대체됨'};
const changeLabels = {added:'추가',modified:'수정',conversation:'대화 저장'};
const stages = [['queued','대기','#9aa9bf'],['reading','읽기 · 계획','#6696db'],['writing','위키 작성','#7e77d3'],['review','검증','#c49b53'],['done','완료','#4f987f']];
const phaseLabels = {queued:'원문 대기',reading:'읽기 · 계획',writing:'위키 작성',review:'검증 대기',done:'검증 완료',blocked:'확인 필요'};
const procedure = ['inspect_contract_and_index','inspect_source_and_existing_scope','semantic_plan_frozen','register_or_resolve_source','update_source_page','update_affected_pages','refresh_index_and_log','validate_structure','final_review_completed'];
const niceBlocker = {PROCEDURE_STAGE_MISSING:'아직 진행하지 않은 단계가 있어요.',PROCEDURE_STAGE_STALE:'위키가 변경되어 검증을 다시 확인해야 해요.',STRUCTURAL_VALIDATION_FAILED:'문서 구조 검증을 통과하지 못했어요.',FINAL_REVIEW_NOT_READY:'최종 검토에서 확인할 내용이 있어요.'};
function utf8Size(value) {
  const text=String(value);
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(text).length;
  try { return encodeURIComponent(text).replace(/%[0-9A-F]{2}|./gi,'x').length; } catch { return text.length*3; }
}

const retrievalUsageTools = WikiStudioModules.createRetrievalUsage({escapeHTML});
const historyCodec = WikiStudioModules.createHistoryCodec({
  limits:{conversations:LOCAL_CONVERSATION_LIMIT,messages:LOCAL_MESSAGE_LIMIT,messageText:LOCAL_MESSAGE_TEXT_LIMIT,evidence:LOCAL_EVIDENCE_LIMIT,excerpt:LOCAL_EXCERPT_LIMIT,explorationEvents:LOCAL_EXPLORATION_EVENT_LIMIT,explorationText:LOCAL_EXPLORATION_TEXT_LIMIT,storageBytes:LOCAL_STORAGE_BYTES_LIMIT},
  byteSize:utf8Size, normalizeRetrievalUsage:retrievalUsageTools.normalize
});
const markdownRenderer = WikiStudioModules.createMarkdownRenderer({escapeHTML,knownDocumentIds:references=>allKnownDocumentIds(references)});
const graphTools = WikiStudioModules.createGraphTools({escapeHTML});
const {boundedText,boundedCount,normalizeContentHash,normalizeReadRanges,normalizeReference,normalizeReferences,normalizeSaved,normalizeExploration,normalizeConversation} = historyCodec;
const {lanes:retrievalUsageLanes,normalize:normalizeRetrievalUsage,retrievalUsageShares,render:renderRetrievalUsage,renderCandidates,explorationEventLabel,renderExploration} = retrievalUsageTools;
const isFiniteNonnegativeInteger = value => typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;


function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { element.hidden = true; }, 4200);
}

async function api(path, body) {
  const options = {headers:{'X-Dashboard-Token':token}};
  if (body !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch('/api/' + path, options);
  let data;
  try { data = await response.json(); } catch { throw new Error('서버 응답을 읽지 못했습니다.'); }
  if (!response.ok) { const error=new Error(data.error || '요청을 처리하지 못했습니다.'); error.status=response.status; error.data=data; throw error; }
  return data;
}

function currentSource() { return state?.sources?.find(source => source.id === selected); }
function isRunning() { return ['running','starting','stopping'].includes(state?.job?.status); }
function isProject() { return state?.mode === 'project'; }
function storageKey(root) { return `doctology.wiki-studio.chat.v2:${String(root || '__example__')}`; }
function storageAvailable() { return typeof localStorage !== 'undefined'; }
function makeConversation() { return {id:`local-${Date.now()}-${Math.random().toString(36).slice(2,8)}`,title:'새 대화',createdAt:Date.now(),updatedAt:Date.now(),messages:[],saves:[],job:null,error:''}; }
function currentConversation() { return conversations.find(conversation => conversation.id === activeConversationId) || null; }
function storageNotice(message) {
  if (historyStorageNotice !== message) toast(message);
  historyStorageNotice = message;
}
function buildHistoryPayload() { return historyCodec.buildHistoryPayload(conversations,activeConversationId); }
function saveHistory() {
  if (!historyRoot) return false;
  if (!storageAvailable()) { storageNotice('브라우저 저장소를 사용할 수 없어 이 대화는 현재 탭에만 유지됩니다.'); return false; }
  const payload=buildHistoryPayload();
  try {
    localStorage.setItem(storageKey(historyRoot),payload.json);
    if (payload.truncated) storageNotice('브라우저 저장 한도에 맞춰 긴 메시지나 오래된 대화 일부만 로컬에 저장했습니다.');
    else historyStorageNotice='';
    return true;
  } catch {
    storageNotice('대화를 브라우저에 저장하지 못했습니다. 저장 공간을 확인하세요. 현재 탭의 대화는 아직 유지됩니다.');
    return false;
  }
}
function loadHistoryForRoot(root) {
  historyRoot = String(root || '__example__');
  conversations = [];
  activeConversationId = '';
  historyStorageNotice = '';
  if (storageAvailable()) {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey(historyRoot)) || 'null');
      if (stored && Array.isArray(stored.conversations)) conversations = stored.conversations.slice(0,LOCAL_CONVERSATION_LIMIT).map(normalizeConversation);
      if (stored?.activeConversationId && conversations.some(item => item.id === stored.activeConversationId)) activeConversationId = stored.activeConversationId;
      if (stored?.truncated) storageNotice('이 워크스페이스의 로컬 기록은 저장 한도에 맞춰 일부만 보관되어 있습니다.');
    } catch { conversations = []; storageNotice('저장된 대화 기록을 읽지 못해 새 로컬 대화를 시작합니다.'); }
  }
  if (!activeConversationId && conversations.length) activeConversationId = conversations[0].id;
  selectedAnswerIndex = latestAssistantIndex(currentConversation());
}
function ensureConversation() {
  let conversation = currentConversation();
  if (!conversation) {
    conversation = makeConversation();
    conversations.unshift(conversation);
    activeConversationId = conversation.id;
    saveHistory();
  }
  return conversation;
}
function latestAssistantIndex(conversation) {
  if (!conversation) return -1;
  for (let index = conversation.messages.length - 1; index >= 0; index -= 1) if (conversation.messages[index].role === 'assistant') return index;
  return -1;
}
function titleConversation(conversation) {
  const first = conversation.messages.find(message => message.role === 'user')?.content.trim();
  conversation.title = first ? (first.length > 34 ? first.slice(0,33) + '…' : first) : '새 대화';
}
function guardChatNavigation() {
  if (!activeChatJob) return true;
  toast('응답 생성이 끝나거나 중단된 뒤 대화를 변경할 수 있습니다.');
  return false;
}
function newConversation() {
  if (!guardChatNavigation()) return false;
  const conversation = makeConversation();
  conversations.unshift(conversation);
  activeConversationId = conversation.id;
  selectedAnswerIndex = -1;
  saveHistory();
  renderChat();
  renderHistory();
  renderKnowledgeGraph();
  renderReferences();
  $('#chat-input').focus?.();
  return true;
}
function clearHistory() {
  if (!guardChatNavigation()) return false;
  if (typeof confirm === 'function' && !confirm('이 워크스페이스의 로컬 대화 기록을 모두 지울까요?')) return false;
  conversations = [];
  activeConversationId = '';
  return newConversation();
}
function selectConversation(id) {
  if (id === activeConversationId) return true;
  if (!guardChatNavigation()) return false;
  if (!conversations.some(conversation => conversation.id === id)) return false;
  activeConversationId = id;
  selectedAnswerIndex = latestAssistantIndex(currentConversation());
  saveHistory(); renderChat(); renderReferences(); renderKnowledgeGraph(); resumeChatIfNeeded();
  return true;
}

function graphNodeTitle(id) { return state?.graph?.nodes?.find(node => node.id === id)?.title || state?.sources?.find(source => source.id === id)?.title || String(id).split('/').at(-1); }
function activeAnswer() {
  const conversation = currentConversation();
  if (!conversation) return null;
  const index = selectedAnswerIndex >= 0 && conversation.messages[selectedAnswerIndex]?.role === 'assistant' ? selectedAnswerIndex : latestAssistantIndex(conversation);
  return index >= 0 ? {...conversation.messages[index],index} : null;
}
function currentRoot() { return String(state?.root || historyRoot || ''); }
function parallelJob() { return state?.job?.parallel && typeof state.job.parallel === 'object' ? state.job.parallel : null; }
function parallelWorker(sourceId) { const worker=parallelJob()?.workers?.find(item => String(item?.source) === String(sourceId)); return worker?.status ? worker : null; }
function parallelActive() { const phase=parallelJob()?.phase; return Boolean(phase && !['stopped','prepared'].includes(phase)); }
function workerOperationStage(worker) { return ({pending:'queued',reading:'reading',drafting:'writing',prepared:'writing'})[worker?.status] || null; }
function workerLabel(worker, source=null) { if (worker?.cleanupPending) return '중단 처리 중'; if (worker?.status==='prepared'&&source?.stage==='done') return '초안 준비됨'; return ({pending:'대기열',reading:'읽는 중',drafting:'초안 작성 중',prepared:'초안 준비됨 · 통합 대기',failed:'실패',stopped:'중단됨',interrupted:'중단됨'})[worker?.status] || ''; }
function workerBadge(worker, source=null) { return worker ? '<span class="worker-badge '+escapeHTML(worker.status||'unknown')+'">'+escapeHTML(workerLabel(worker,source))+'</span>' : ''; }
function sourceOperationStage(source) { const worker=parallelWorker(source?.id),operation=workerOperationStage(worker); return parallelActive() && operation ? operation : source?.stage; }
function certifiedSourceLabel(source) { return source?.stage==='done' ? '검증 완료' : (phaseLabels[source?.stage] || source?.stage || ''); }
function parallelPreparationAvailable() { return state?.parallelPreparationAvailable===true && taskMode==='start' && !state?.demo && !isProject(); }
function allRequestedSourcesVerified(job=state?.job) { const requested=Array.isArray(job?.sources)?job.sources:[]; return requested.length>0&&requested.every(item=>{const id=typeof item==='string'?item:(item?.id||item?.source);return state?.sources?.find(source=>source.id===id)?.stage==='done';}); }
function stateSignature(value) { return JSON.stringify({...value,checkedAt:0,automation:value?.automation?{...value.automation,checkedAt:0}:value?.automation}); }
function queuePageInfo(page,rowCount=0) {
  const limit=Math.max(1,Number(page?.limit)||100),total=Math.max(0,Number(page?.total)||rowCount),reported=Math.max(0,Number(page?.offset)||0),maxOffset=total?Math.floor((total-1)/limit)*limit:0;
  return {offset:Math.min(reported,maxOffset),limit,total};
}
function clampedQueueOffset(page) { return queuePageInfo(page).offset; }
function queueItem(id) { return (state?.automation?.queue || []).find(item => String(item.id) === String(id)) || null; }
function queueTargets(item) { return Array.isArray(item?.targets) ? item.targets.map(target => typeof target === 'string' ? {id:target,title:graphNodeTitle(target)} : target).filter(target => target?.id) : []; }
function formatElapsed(item, now = Date.now()) {
  const start=Number(item?.startedAt || item?.createdAt || 0)*1000,end=Number(item?.endedAt || item?.updatedAt || 0)*1000;
  if (!start) return '시간 기록 없음';
  const live=['pending','running'].includes(item?.status),seconds=Math.max(0,Math.floor(((live?now:end||now)-start)/1000));
  if (seconds<60) return `${seconds}초`;
  const minutes=Math.floor(seconds/60),rest=seconds%60;
  return `${minutes}분 ${rest}초`;
}
function savedSummary(saved) {
  if (!saved) return '';
  const item=queueItem(saved.itemId),status=item?.status || 'unknown',completed=status==='completed';
  const label=completed?'위키 정리 완료 · 기존 게이트 통과':status==='running'?'원문 보존 · 위키 정리 중':status==='needs_attention'?'원문 보존 · 확인 필요':status==='unknown'?'원문 보존 · 대기열 상태 확인 필요':'원문 보존 · 위키 정리 대기';
  const targets=completed?queueTargets(item):[];
  return `<div class="saved-summary ${escapeHTML(status)}"><div><strong>${escapeHTML(label)}</strong><span>${escapeHTML(item?.reason || (completed?'서버의 완료 상태와 실제 대상을 확인했습니다.':status==='unknown'?'현재 상태 응답에 이 작업이 없어 완료로 간주하지 않습니다.':'저장은 완료됐지만 아직 검증된 위키 지식이 아닙니다.'))}</span></div><div class="saved-actions"><button data-page="${escapeHTML(saved.sourcePath)}">원문 보기</button><button data-action="show-watch">작업 보기</button>${targets.map(target=>`<button data-page="${escapeHTML(target.id)}">${escapeHTML(target.title||target.id)}</button>`).join('')}</div></div>`;
}
function answerPair(conversation,index) {
  if (!conversation?.messages[index] || conversation.messages[index].role!=='assistant') throw new Error('저장할 답변을 선택해 주세요.');
  let questionIndex=index-1;
  while (questionIndex>=0 && conversation.messages[questionIndex].role!=='user') questionIndex-=1;
  if (questionIndex<0) throw new Error('선택한 답변의 질문을 찾지 못했습니다.');
  return [conversation.messages[questionIndex],conversation.messages[index]];
}
function chatSaveMessages(scope='answer',answerIndex=selectedAnswerIndex) {
  const conversation=currentConversation();
  if (!conversation) throw new Error('저장할 대화가 없습니다.');
  if (scope==='conversation' && conversation.historyTruncated) throw new Error('로컬 기록이 일부만 남아 있어 전체 대화를 저장할 수 없습니다. 원본 대화에서 다시 시도해 주세요.');
  const source=scope==='conversation'?conversation.messages:answerPair(conversation,answerIndex);
  if (!source.length) throw new Error('저장할 대화가 없습니다.');
  if (source.some(message=>message.truncated)) throw new Error('잘린 로컬 메시지는 불완전한 원문으로 저장하지 않습니다. 원본이 남아 있는 대화에서 다시 시도해 주세요.');
  if (source.length>CHAT_SAVE_MESSAGE_LIMIT) throw new Error(`한 번에 ${CHAT_SAVE_MESSAGE_LIMIT}개 메시지까지 저장할 수 있습니다.`);
  if (!source.some(message=>message.role==='user') || !source.some(message=>message.role==='assistant')) throw new Error('사용자 질문과 어시스턴트 답변이 모두 있어야 저장할 수 있습니다.');
  const messages=source.map(message=>{
    const content=String(message.content||''); if(content.length>50000)throw new Error('메시지 하나는 50,000자 이하여야 저장할 수 있습니다.');
    const references=message.role==='assistant'&&message.references?.length?normalizeReferences(message.references).filter(reference=>reference.id).map((reference,index)=>({id:reference.id,title:reference.title,number:Number.isInteger(reference.number)&&reference.number>=1&&reference.number<=10000?reference.number:index+1,excerpt:reference.excerpt})):[];
    return {role:message.role,content,...(references.length?{references}:{})};
  });
  if (chatSaveCharCount(messages)>CHAT_SAVE_CHARS_LIMIT) throw new Error('대화와 참고문헌이 100,000자를 넘어 저장할 수 없습니다. 범위를 줄여 주세요.');
  return messages;
}
function chatSaveCharCount(messages,title='') { return String(title).length+messages.reduce((sum,message)=>sum+String(message.content||'').length+(message.references||[]).reduce((subtotal,reference)=>subtotal+String(reference.id||'').length+String(reference.title||'').length+String(reference.excerpt||'').length,0),0); }
function chatSaveReason(answerIndex=selectedAnswerIndex,scope='answer') {
  if (state?.demo) return '예시 작업실에서는 저장하지 않습니다. 내 위키를 연결하세요.';
  if (isProject()) return '프로젝트는 읽기 전용이라 대화를 원문으로 저장할 수 없습니다.';
  try { chatSaveMessages(scope,answerIndex); return ''; } catch(error) { return error.message; }
}
function setChatSaveCommitting(value) {
  chatSaveCommitting=Boolean(value);
  $('#chat-save-title').disabled=chatSaveCommitting;
  $$('input[name="scope"]',$('#chat-save-form')).forEach(input=>{input.disabled=chatSaveCommitting;});
  $('#chat-preview-refresh').disabled=chatSaveCommitting;
  $('#chat-save-submit').disabled=chatSaveCommitting||!savePreview;
}
function invalidateSavePreview({close=false}={}) {
  savePreviewGeneration+=1; clearTimeout(savePreviewTimer); savePreviewTimer=0; savePreview=null; saveContext=null; chatSaveRecovery=null;
  const dialog=$('#chat-save-dialog'); if(close&&dialog?.open)dialog.close();
  const preview=$('#chat-save-preview'); if(preview)preview.textContent='미리보기를 다시 만들어 주세요.';
  const submit=$('#chat-save-submit'); if(submit)submit.disabled=true;
}
function markSavePreviewStale() {
  if (!saveContext) return;
  savePreview=null; savePreviewGeneration+=1;
  $('#chat-save-preview').textContent='제목이나 범위가 바뀌었습니다. 서버에서 정확한 Markdown을 다시 만들고 있습니다…';
  $('#chat-save-submit').disabled=true; $('#chat-preview-refresh').hidden=false;
  clearTimeout(savePreviewTimer); savePreviewTimer=setTimeout(()=>requestChatSavePreview(),350);
}
async function requestChatSavePreview(options={}) {
  if (!saveContext) return;
  clearTimeout(savePreviewTimer); savePreviewTimer=0;
  const dialog=$('#chat-save-dialog'),form=$('#chat-save-form');
  const scope=options.scope || $('input[name="scope"]:checked',form)?.value || saveContext.scope || 'answer';
  const title=String(options.title ?? $('#chat-save-title').value ?? '').trim();
  const answerIndex=Number.isInteger(options.answerIndex)?options.answerIndex:saveContext.answerIndex;
  const rootAtStart=currentRoot(),generation=++savePreviewGeneration;
  const error=$('.form-error',dialog); error.textContent='';
  $('#chat-save-submit').disabled=true; $('#chat-preview-refresh').hidden=true; $('#chat-save-preview').textContent='서버에서 정확한 Markdown 미리보기를 만들고 있습니다…';
  try {
    if (!title) throw new Error('원문 제목을 입력해 주세요.');
    if (title.length>200) throw new Error('원문 제목은 200자 이하로 입력해 주세요.');
    const messages=chatSaveMessages(scope,answerIndex);
    if(chatSaveCharCount(messages,title)>CHAT_SAVE_CHARS_LIMIT)throw new Error('제목을 포함한 대화와 참고문헌이 100,000자를 넘어 저장할 수 없습니다.');
    const result=await api('chat-save-preview',{expectedRoot:rootAtStart,title,messages});
    if (generation!==savePreviewGeneration || currentRoot()!==rootAtStart || !dialog.open) return;
    if (String(result.root||'')!==rootAtStart) throw new Error('다른 워크스페이스의 미리보기는 사용할 수 없습니다.');
    saveContext={scope,answerIndex,conversationId:activeConversationId}; chatSaveRecovery=null;
    savePreview={previewId:String(result.previewId),root:rootAtStart,title:String(result.title||title),scope,answerIndex,sourcePath:String(result.sourcePath||''),markdown:String(result.markdown||''),warnings:Array.isArray(result.warnings)?result.warnings.map(String):[],expiresAt:result.expiresAt};
    $('#chat-save-title').value=savePreview.title; $('#chat-save-preview').textContent=savePreview.markdown; $('#chat-save-submit').textContent='위키로 정리 시작';
    $('#chat-save-meta').textContent=`${scope==='conversation'?'현재 대화 전체':'선택한 질문 + 답변'} · ${messages.length}개 메시지 · ${savePreview.sourcePath}`;
    $('#chat-save-warnings').innerHTML=savePreview.warnings.map(warning=>`<p>${escapeHTML(warning)}</p>`).join('');
    $('#chat-save-submit').disabled=false;
  } catch(previewError) {
    if (generation!==savePreviewGeneration || currentRoot()!==rootAtStart) return;
    savePreview=null; error.textContent=previewError.message; $('#chat-save-preview').textContent='미리보기를 만들지 못했습니다. 내용을 유지한 채 다시 시도할 수 있습니다.'; $('#chat-preview-refresh').hidden=false;
  }
}
function openChatSave(answerIndex=selectedAnswerIndex,scope='answer') {
  const reason=chatSaveReason(answerIndex,scope); if(reason){toast(reason);return false;}
  const conversation=currentConversation(),answer=conversation.messages[answerIndex];
  const title=scope==='conversation'?conversation.title:String(answerPair(conversation,answerIndex)[0].content||conversation.title).split('\n')[0].slice(0,120);
  invalidateSavePreview(); saveContext={scope,answerIndex,conversationId:conversation.id}; chatSaveRecovery=null;
  const form=$('#chat-save-form'); $$('input[name="scope"]',form).forEach(input=>{input.checked=input.value===scope;});
  $('#chat-save-title').value=title; $('#chat-save-meta').textContent='원문을 저장하기 전 서버 미리보기를 확인하세요.'; $('#chat-save-warnings').innerHTML='';
  openDialog('#chat-save-dialog'); requestChatSavePreview({scope,title,answerIndex}); return true;
}
async function commitChatSave() {
  if (!savePreview || !saveContext) throw new Error('현재 제목과 범위로 미리보기를 다시 만들어 주세요.');
  const preview={...savePreview,warnings:[...(savePreview.warnings||[])]},context={...saveContext};
  const rootAtStart=currentRoot(),form=$('#chat-save-form'),scope=$('input[name="scope"]:checked',form)?.value || context.scope,title=String($('#chat-save-title').value||'').trim();
  if (rootAtStart!==preview.root || scope!==preview.scope || title!==preview.title) throw new Error('제목이나 범위가 바뀌었습니다. 미리보기를 다시 만들어 주세요.');
  setChatSaveCommitting(true);
  try {
    const result=await api('chat-save',{expectedRoot:rootAtStart,previewId:preview.previewId});
    if (currentRoot()!==rootAtStart) { toast(`이전 워크스페이스에 원문이 저장되고 작업 대기열에 등록되었습니다: ${result.sourcePath||preview.sourcePath}`); return; }
    const item=result.item||{},saved={itemId:String(item.id||''),sourcePath:String(result.sourcePath||preview.sourcePath),root:rootAtStart,savedAt:Date.now(),scope};
    if (!saved.itemId || !saved.sourcePath) throw new Error('서버가 저장된 원문과 대기열 식별자를 반환하지 않았습니다.');
    if (!state.automation) state.automation={available:true,enabled:false,autoRun:false,queue:[],counts:{}};
    if (!state.automation.queue.some(value=>String(value.id)===saved.itemId)) state.automation.queue.unshift(item);
    const conversation=conversations.find(value=>value.id===context.conversationId);
    if (conversation) {
      if (scope==='conversation') { conversation.saves=conversation.saves||[]; if(!conversation.saves.some(value=>value.itemId===saved.itemId))conversation.saves.push(saved); }
      else if (conversation.messages[context.answerIndex]?.role==='assistant') conversation.messages[context.answerIndex].save=saved;
      conversation.updatedAt=Date.now(); saveHistory();
    }
    const dialog=$('#chat-save-dialog'); if(dialog.open)dialog.close(); invalidateSavePreview(); renderChat(); renderAutomation();
    toast(conversation?(result.alreadySaved?'이미 보존된 원문을 작업 대기열에서 확인했습니다.':'원문 보존 · 위키 정리 대기'):'원문과 작업 대기열은 저장됐지만 이 브라우저의 대화 연결은 찾지 못했습니다. 작업 보기에서 확인하세요.');
  } catch(error) {
    error.saveCapture={preview,context,root:rootAtStart};
    if(error.data?.recoverable===true&&error.data?.queueHandoff===false&&currentRoot()===rootAtStart){savePreview=preview;saveContext=context;chatSaveRecovery={sourcePath:String(error.data.sourcePath||preview.sourcePath),root:rootAtStart};$('#chat-save-title').value=preview.title;$('#chat-save-preview').textContent=preview.markdown;$$('input[name="scope"]',$('#chat-save-form')).forEach(input=>{input.checked=input.value===preview.scope;});}
    throw error;
  } finally { setChatSaveCommitting(false); }
}
function handleChatSaveError(error,form=$('#chat-save-form')) {
  const data=error?.data||{},recoverable=data.recoverable===true&&data.queueHandoff===false,sourcePath=String(data.sourcePath||chatSaveRecovery?.sourcePath||'');
  if(recoverable){
    const sameRoot=error.saveCapture?.root===currentRoot();
    if(sameRoot&&savePreview){const dialog=$('#chat-save-dialog');if(!dialog.open)dialog.showModal();$('#chat-save-meta').textContent=`원문 저장됨 · 대기열 등록 재시도 필요 · ${sourcePath}`;$('#chat-save-warnings').innerHTML=`<p>${escapeHTML(data.error||'원문은 저장됐지만 작업 대기열에 등록되지 않았습니다.')}</p>`;$('#chat-save-submit').textContent='대기열 등록 다시 시도';$('#chat-save-submit').disabled=false;}
    $('.form-error',form).textContent=data.error||error.message;
    toast(sameRoot?'원문은 저장됐습니다. 같은 미리보기로 대기열 등록을 다시 시도하세요.':`이전 워크스페이스에 원문이 저장됐지만 대기열 등록이 필요합니다: ${sourcePath}`);
    return true;
  }
  $('.form-error',form).textContent=error.message; $('#chat-save-submit').disabled=!savePreview; return false;
}
function allKnownDocumentIds(references = []) {
  const ids = new Set([...(state?.graph?.nodes || []).map(node => node.id),...(state?.sources || []).map(source => source.id),...documentLinks]);
  for (const reference of references) {
    if (reference.id) ids.add(reference.id);
    for (const raw of reference.rawSources || []) if (raw.id) ids.add(raw.id);
  }
  return ids;
}
const resolveInternalLink = markdownRenderer.resolveInternalLink;
const renderInline = markdownRenderer.renderInline;
const renderMarkdown = markdownRenderer.renderMarkdown;
const renderAnswerMarkdown = markdownRenderer.renderAnswerMarkdown;

const suggestedPrompts = () => markdownRenderer.suggestedPrompts(state?.graph?.nodes);
const renderEmptyChat = () => markdownRenderer.renderEmptyChat(state,icon);
function elapsedChatSeconds(job, now = Date.now()) {
  return Math.max(0,Math.floor((now-(Number(job?.startedAt)||now))/1000));
}
function renderPendingAnswer() {
  if (!activeChatJob) return '';
  const references=activeChatJob.references||[],answer=String(activeChatJob.answer||''),exploration=activeChatJob.exploration,elapsed=elapsedChatSeconds(activeChatJob);
  const readLabel=exploration?'읽은 문서':'검색 후보';
  return `<article class="message assistant-message pending"><div class="assistant-avatar">D</div><div class="assistant-content"><div class="message-label">DocTology · ${elapsed}초</div>${answer?`<div class="answer-body partial-answer">${renderAnswerMarkdown(answer,references)}</div><div class="provisional-note">생성 중인 초안입니다. 인용과 문장은 완료 전 바뀔 수 있습니다.</div>`:`<div class="thinking"><i></i><span>위키에서 근거를 찾고 있습니다</span></div>`}${renderRetrievalUsage(exploration?.retrievalUsage)}${renderExploration(exploration)}${activeChatJob.candidates?.length?`<div class="pending-candidates">${readLabel} ${activeChatJob.candidates.length}개 · 아직 답변의 인용이 아닙니다</div>`:''}</div></article>`;
}
function updateChatScrollControls() {
  const area=$('#chat-messages'),maximum=Math.max(0,(Number(area.scrollHeight)||0)-(Number(area.clientHeight)||0));
  const top=Math.max(0,Number(area.scrollTop)||0);
  $('#chat-scroll-controls').hidden=maximum<=2;
  $('#chat-scroll-top').disabled=top<=2;
  $('#chat-scroll-bottom').disabled=maximum-top<=2;
}
function jumpChat(destination) {
  const area=$('#chat-messages');
  const reduced=typeof matchMedia==='function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  area.scrollTo({top:destination==='top'?0:area.scrollHeight,behavior:reduced?'instant':'smooth'});
}
function observeChatScroll() {
  updateChatScrollControls();
  if (!chatScrollObserver && typeof ResizeObserver!=='undefined') chatScrollObserver=new ResizeObserver(updateChatScrollControls);
  if (chatScrollObserver) {
    const area=$('#chat-messages');
    chatScrollObserver.disconnect(); chatScrollObserver.observe(area);
    if (area.firstElementChild) chatScrollObserver.observe(area.firstElementChild);
  }
}
function chatDisclosureKey(detail) {
  const owner=detail.closest?.('[data-answer-index]');
  return `${owner?.dataset?.answerIndex ?? 'pending'}:${detail.classList.contains('candidate-box')?'candidates':'tools'}`;
}
function renderChat() {
  const container = $('#chat-messages');
  const conversation = ensureConversation();
  const ownerKey=`${historyRoot}:${conversation.id}`;
  const openDisclosures=new Set(renderedChatOwner===ownerKey ? [...container.querySelectorAll('details[open]')].map(chatDisclosureKey) : []);
  renderedChatOwner=ownerKey;
  if (!activeChatJob && openDisclosures.has('pending:tools')) openDisclosures.add(`${latestAssistantIndex(conversation)}:tools`);
  const chatUnavailable = state?.chatAvailable === false;
  if (!conversation.messages.length && !activeChatJob) container.innerHTML = renderEmptyChat();
  else {
    const wholeReason=chatSaveReason(latestAssistantIndex(conversation),'conversation');
    const conversationSaves=(conversation.saves||[]).map(savedSummary).join('');
    container.innerHTML = `<div class="message-stack"><div class="conversation-save-bar"><div><strong>현재 대화를 원문으로 보존</strong><span>검증된 사실이 아니며 저장 뒤 기존 게이트를 통과해야 합니다.</span></div><button data-action="save-conversation" ${wholeReason?'disabled':''} title="${escapeHTML(wholeReason||'현재 대화 전체를 미리보고 저장')}">대화 전체 저장</button></div>${conversationSaves}${conversation.messages.map((message,index) => message.role === 'user'
      ? `<article class="message user-message"><div class="message-label">나</div><div class="user-bubble">${escapeHTML(message.content)}</div></article>`
      : (()=>{const saveReason=chatSaveReason(index,'answer');return `<article class="message assistant-message ${selectedAnswerIndex===index?'focused':''}" data-answer-index="${index}" tabindex="0"><div class="assistant-avatar">D</div><div class="assistant-content"><div class="message-label">DocTology</div><div class="answer-body">${renderAnswerMarkdown(message.content,message.references)}</div>${renderRetrievalUsage(message.exploration?.retrievalUsage)}${message.truncated?'<div class="provisional-note">로컬 저장 한도 때문에 이 메시지의 뒷부분은 저장되지 않았습니다. 불완전한 원문으로 내보내지 않습니다.</div>':''}${message.partial?'<div class="provisional-note">응답 연결이 종료되어 마지막으로 받은 초안입니다. 완료된 답변이 아닙니다.</div>':''}${renderExploration(message.exploration)}${renderCandidates(message.candidates,message.exploration)}<div class="answer-actions">${message.references?.length ? `<button class="answer-reference-summary" data-answer-index="${index}">참고문헌 ${message.references.length}개 보기</button>` : '<span class="no-citations">이 답변에는 명시된 인용이 없습니다.</span>'}<button class="answer-save-button" data-save-answer="${index}" ${saveReason?'disabled':''} title="${escapeHTML(saveReason||'이 질문과 답변을 원문으로 미리보기')}">위키에 저장</button></div><p class="unverified-chat-note">대화 저장은 사실 검증이나 위키 완료를 뜻하지 않습니다.</p>${savedSummary(message.save)}</div></article>`;})()).join('')}${renderPendingAnswer()}${conversation.error ? `<div class="chat-error" role="alert"><span>${escapeHTML(conversation.error)}</span><button data-action="${activeChatJob?'reconnect-chat':'retry-chat'}">${activeChatJob?'연결 다시 확인':'다시 시도'}</button></div>` : ''}</div>`;
  }
  for (const detail of container.querySelectorAll('details')) {
    if (openDisclosures.has(chatDisclosureKey(detail))) detail.open=true;
  }
  $('#chat-work-notice').hidden = Boolean(state?.demo) || !(isRunning() || state?.job?.status === 'external');
  $('#chat-submit').disabled = Boolean(activeChatJob) || chatUnavailable;
  $('#chat-stop').hidden = !activeChatJob;
  $('#chat-status').textContent = activeChatJob ? `${elapsedChatSeconds(activeChatJob)}초 · 응답 생성 중` : chatUnavailable ? '위키 연결과 Pi 설정이 필요합니다' : historyStorageNotice;
  $('.new-conversation').disabled = Boolean(activeChatJob);
  $('[data-action="clear-history"]').disabled = Boolean(activeChatJob);
  renderHistory();
  observeChatScroll();
}
function renderHistory() {
  const list = $('#chat-history');
  list.innerHTML = conversations.length ? conversations.slice().sort((a,b)=>b.updatedAt-a.updatedAt).map(conversation => `<button class="history-item ${conversation.id===activeConversationId?'active':''}" data-conversation="${escapeHTML(conversation.id)}" ${activeChatJob?'disabled aria-disabled="true" title="응답 생성 중에는 대화를 변경할 수 없습니다"':''}><span>${escapeHTML(conversation.title)}</span><small>${new Date(conversation.updatedAt).toLocaleDateString('ko-KR',{month:'short',day:'numeric'})}</small></button>`).join('') : '<p class="history-empty">아직 저장된 대화가 없습니다.</p>';
}
function focusAnswer(index) {
  const conversation = currentConversation();
  if (!conversation?.messages[index] || conversation.messages[index].role !== 'assistant') return;
  selectedAnswerIndex = index;
  renderChat();
  renderReferences();
  renderKnowledgeGraph();
}
function renderReferences() {
  const answer = activeAnswer();
  const references = answer?.references || [];
  $('#reference-count').textContent = String(references.length);
  $('#reference-context').textContent = answer ? (references.length ? '선택한 답변이 명시한 참고문헌입니다.' : '선택한 답변에는 명시된 참고문헌이 없습니다.') : '답변의 번호 인용을 선택하면 원문을 확인할 수 있습니다.';
  $('#answer-references').innerHTML = references.length ? references.map(reference => `<article class="reference-card"><button class="reference-main" data-reference-id="${escapeHTML(reference.id)}"><span class="reference-number">${reference.number}</span><span><strong>${escapeHTML(reference.title)}</strong>${reference.excerpt ? `<small>${escapeHTML(reference.excerpt)}</small>` : ''}</span></button>${reference.rawSources.length ? `<div class="raw-source-list"><span>연결된 원문</span>${reference.rawSources.map(raw => `<button data-page="${escapeHTML(raw.id)}">${escapeHTML(raw.title)}</button>`).join('')}</div>` : ''}</article>`).join('') : '<div class="reference-empty"><span>인용은 답변 후 여기에 표시됩니다.</span><small>검색 후보는 참고문헌으로 간주하지 않습니다.</small></div>';
}
function referencesForActiveAnswer() { return activeAnswer()?.references || []; }
const edgeKey = graphTools.edgeKey;
function citationGraphFocus() { return graphTools.citationFocus({nodes:state?.graph?.nodes||[],edges:state?.graph?.edges||[],references:referencesForActiveAnswer()}); }
const positions = graphTools.positions;
const normalizeGraphPositions = graphTools.normalizePositions;
function renderKnowledgeGraph() { return graphTools.renderKnowledgeGraph({state,references:referencesForActiveAnswer(),$,limit:GRAPH_LIMIT}); }

const chatHistoryPayload = historyCodec.chatHistoryPayload;
async function submitChat(message, {reuseLast=false} = {}) {
  const text = String(message || '').trim();
  if (!text || activeChatJob) return;
  if (state?.chatAvailable === false) { toast('위키를 연결하고 Pi 설정을 확인해 주세요.'); return; }
  if (text.length > 8000) { toast('질문은 8,000자 이하로 입력해 주세요.'); return; }
  const conversation = ensureConversation();
  conversation.error = '';
  let historyMessages = conversation.messages;
  if (reuseLast) {
    const last = conversation.messages.at(-1);
    if (!last || last.role !== 'user' || last.content !== text) return;
    historyMessages = conversation.messages.slice(0,-1);
  } else {
    historyMessages = [...conversation.messages];
    conversation.messages.push({role:'user',content:text,createdAt:Date.now()});
  }
  titleConversation(conversation);
  conversation.updatedAt = Date.now();
  const rootAtStart = String(state?.root || historyRoot);
  activeChatJob = {id:'starting',conversationId:conversation.id,root:rootAtStart,status:'starting',startedAt:Date.now(),answer:'',references:[],candidates:[],exploration:null};
  saveHistory(); renderChat(); renderReferences(); renderKnowledgeGraph();
  try {
    const model = String($('#chat-model').value || '').trim();
    const body = {message:text,history:chatHistoryPayload(historyMessages)};
    if (model) body.model = model;
    const started = await api('chat',body);
    if (String(state?.root || historyRoot) !== rootAtStart || activeConversationId !== conversation.id) { activeChatJob = null; return; }
    activeChatJob = {id:String(started.id),conversationId:conversation.id,root:rootAtStart,status:String(started.status || 'running'),startedAt:activeChatJob.startedAt,answer:'',references:[],candidates:[],exploration:normalizeExploration(started.exploration)};
    conversation.job = {id:activeChatJob.id,status:activeChatJob.status,startedAt:activeChatJob.startedAt};
    saveHistory(); renderChat();
    pollChat(activeChatJob.id,rootAtStart,conversation.id);
  } catch (error) {
    activeChatJob = null;
    conversation.job = null;
    conversation.error = error.message;
    conversation.updatedAt = Date.now();
    saveHistory(); renderChat();
  }
}
function preservePartialChat(conversation, message) {
  if (!conversation || !activeChatJob?.answer) return;
  conversation.messages.push({role:'assistant',content:activeChatJob.answer,references:activeChatJob.references||[],candidates:activeChatJob.candidates||[],exploration:activeChatJob.exploration||null,partial:true,createdAt:Date.now()});
  selectedAnswerIndex=conversation.messages.length-1;
  conversation.error=message;
}
function clearConfirmedChatHandle(conversation, message) {
  preservePartialChat(conversation,message);
  activeChatJob=null;
  if (conversation) { conversation.job=null; conversation.updatedAt=Date.now(); saveHistory(); }
  renderChat(); renderReferences(); renderKnowledgeGraph();
}
function chatPollDelay(failures) { return Math.min(5000,CHAT_POLL_BACKOFF_MS * (2 ** Math.max(0,failures-1))); }
async function pollChat(id, rootAtStart, conversationId) {
  const generation = ++chatPollGeneration;
  const initialConversation=conversations.find(item => item.id === conversationId);
  if (initialConversation && !initialConversation.job && activeChatJob?.id === id) initialConversation.job={id,status:activeChatJob.status||'running',startedAt:activeChatJob.startedAt||Date.now()};
  while (generation === chatPollGeneration && activeChatJob?.id === id) {
    try {
      const result = await api('chat?id=' + encodeURIComponent(id));
      if (generation !== chatPollGeneration || String(state?.root || historyRoot) !== rootAtStart) return;
      const conversation = conversations.find(item => item.id === conversationId);
      if (!conversation) return;
      if (result.root && String(result.root) !== rootAtStart) { clearConfirmedChatHandle(conversation,'이 응답은 다른 워크스페이스에서 시작되어 마지막 수신 초안만 보존했습니다.'); return; }
      const status = String(result.status || 'failed');
      const serverStartedAt=Number(result.startedAt)?Number(result.startedAt)*1000:activeChatJob.startedAt;
      conversation.job = {id,status,startedAt:serverStartedAt};
      if (status === 'running') {
        activeChatJob.status=status; activeChatJob.startedAt=serverStartedAt; activeChatJob.answer=String(result.answer||'');
        activeChatJob.references=normalizeReferences(result.references);
        activeChatJob.candidates=normalizeReferences(result.candidates);
        activeChatJob.exploration=normalizeExploration(result.exploration);
        activeChatJob.pollFailures=0;
        conversation.error='';
        saveHistory(); renderChat(); await new Promise(resolve => setTimeout(resolve,CHAT_POLL_BACKOFF_MS)); continue;
      }
      activeChatJob = null;
      conversation.job = null;
      conversation.updatedAt = Date.now();
      if (status === 'finished') {
        conversation.messages.push({role:'assistant',content:String(result.answer || ''),references:normalizeReferences(result.references),candidates:normalizeReferences(result.candidates),exploration:normalizeExploration(result.exploration),createdAt:Date.now()});
        conversation.error = '';
        selectedAnswerIndex = conversation.messages.length - 1;
      } else if (status === 'stopped') conversation.error = '응답 생성을 중단했습니다. 질문은 대화에 남아 있습니다.';
      else conversation.error = String(result.error || '답변을 만들지 못했습니다.');
      saveHistory(); renderChat(); renderReferences(); renderKnowledgeGraph(); return;
    } catch (error) {
      if (generation !== chatPollGeneration || activeChatJob?.id !== id) return;
      const conversation = conversations.find(item => item.id === conversationId);
      if (error?.status === 404) { clearConfirmedChatHandle(conversation,'응답 작업을 서버에서 찾을 수 없어 마지막 수신 초안만 보존했습니다.'); return; }
      const failures=(activeChatJob.pollFailures||0)+1;
      activeChatJob.pollFailures=failures;
      if (conversation) { conversation.error=failures>=CHAT_POLL_FAILURE_LIMIT?'응답 연결을 다시 확인하지 못했습니다. 작업은 계속 실행 중일 수 있습니다. 연결 다시 확인 또는 응답 중단을 선택하세요.':`응답 연결을 다시 확인하는 중입니다. (${failures}/${CHAT_POLL_FAILURE_LIMIT}) ${error.message}`; conversation.updatedAt=Date.now(); saveHistory(); }
      renderChat();
      if (failures>=CHAT_POLL_FAILURE_LIMIT) return;
      await new Promise(resolve => setTimeout(resolve,chatPollDelay(failures)));
    }
  }
}
async function reconnectChat() {
  if (!activeChatJob || activeChatJob.id === 'starting') return;
  const conversation=conversations.find(item=>item.id===activeChatJob.conversationId);
  if (conversation) { conversation.error=''; conversation.updatedAt=Date.now(); }
  activeChatJob.pollFailures=0;
  saveHistory(); renderChat();
  await pollChat(activeChatJob.id,activeChatJob.root,activeChatJob.conversationId);
}
function resumeChatIfNeeded() {
  const conversation = currentConversation();
  if (!conversation?.job || !['running','starting'].includes(conversation.job.status) || activeChatJob) return;
  activeChatJob = {id:conversation.job.id,conversationId:conversation.id,root:historyRoot,status:'running',startedAt:conversation.job.startedAt||Date.now(),answer:'',references:[],candidates:[],exploration:null};
  renderChat();
  pollChat(activeChatJob.id,historyRoot,conversation.id);
}
async function stopChat() {
  if (!activeChatJob || activeChatJob.id === 'starting') return;
  const stoppedId=activeChatJob.id;
  await api('chat-stop',{id:stoppedId});
  if (activeChatJob?.id !== stoppedId) return;
  $('#chat-status').textContent = '중단 요청 중';
  // Polling may have paused after repeated transport failures; reclaim terminal state.
  if (activeChatJob) await reconnectChat();
}

const retrievalStatusTools = WikiStudioModules.createRetrievalStatusTools({escapeHTML});
const {normalizeRetrievalStatus} = retrievalStatusTools;
function renderRetrievalStatus() { return retrievalStatusTools.renderRetrievalStatus({state,retrievalStatus,retrievalStatusRoot,$}); }
function requestRetrievalStatus(force = false) {
  const root=String(state?.root || '');
  if (!root || state?.demo || document.hidden) return Promise.resolve(null);
  const now=Date.now();
  if (retrievalStatusRequest) return retrievalStatusRequest;
  if (!force && retrievalStatusRoot===root && retrievalStatus && now-retrievalStatusLastRequestedAt<RETRIEVAL_STATUS_POLL_MS) return Promise.resolve(retrievalStatus);
  const generation=retrievalStatusGeneration;
  retrievalStatusLastRequestedAt=now;
  const request=api('retrieval-status',{expectedRoot:root,force:Boolean(force)}).then(value=>{
    const normalized=normalizeRetrievalStatus(value,root);
    if (generation!==retrievalStatusGeneration || String(state?.root||'')!==root) return null;
    retrievalStatusRoot=root; retrievalStatus=normalized||{kind:'error'}; renderRetrievalStatus(); return retrievalStatus;
  }).catch(error=>{
    if (generation!==retrievalStatusGeneration || String(state?.root||'')!==root) return null;
    retrievalStatusRoot=root; retrievalStatus={kind:error.status===404?'unsupported':'error'}; renderRetrievalStatus(); return retrievalStatus;
  }).finally(()=>{if(retrievalStatusRequest===request)retrievalStatusRequest=null;});
  retrievalStatusRequest=request;
  return request;
}
function resetRetrievalStatus(root) { retrievalStatusGeneration+=1; retrievalStatusRequest=null; retrievalStatusLastRequestedAt=0; retrievalStatus=null; retrievalStatusRoot=String(root||''); }

async function refresh(force = false) {
  if (loading) return;
  loading = true;
  try {
    const requestedOffset=watchQueueOffset;
    let next = await api(requestedOffset?`state?queueOffset=${encodeURIComponent(requestedOffset)}`:'state');
    let rootChanged = String(next.root || '__example__') !== historyRoot;
    if(rootChanged&&requestedOffset){watchQueueOffset=0;next=await api('state');rootChanged=String(next.root || '__example__') !== historyRoot;}
    if(rootChanged)watchQueueOffset=0;else watchQueueOffset=clampedQueueOffset(next.automation?.queuePage);
    $('#error-banner').hidden = true;
    $('#connection').textContent = next.demo ? '예시 미리보기' : next.mode === 'project' ? '프로젝트 · 읽기 전용' : '로컬 위키 연결됨';
    $('#connection').classList.toggle('live', !next.demo);
    const signature = stateSignature(next);
    state = next;
    if (rootChanged) {
      resetDocumentReader();
      resetRetrievalStatus(next.root);
      invalidateSavePreview({close:true});
      watchDraft=null; watchQueueOffset=0;
      chatPollGeneration += 1;
      activeChatJob = null;
      loadHistoryForRoot(next.root || '__example__');
      view = 'chat';
    }
    if (force || signature !== lastRender || rootChanged) { lastRender = signature; render(); }
    requestRetrievalStatus(false);
    $('#last-checked').textContent = state.demo ? '예시 데이터 · 실행하지 않음' : `${new Date((state.checkedAt || Date.now()/1000)*1000).toLocaleTimeString('ko-KR')} 기준`;
    resumeChatIfNeeded();
  } catch (error) {
    $('#error-banner').textContent = `연결이 끊겼습니다. 마지막 표시 상태가 최신이 아닐 수 있어요. ${error.message}`;
    $('#error-banner').hidden = false;
    $('#connection').textContent = '연결 끊김';
    $('#connection').classList.remove('live');
  } finally { loading = false; }
}
function render() {
  $('#workspace-name').textContent = state.name;
  $('#workspace-caption').textContent = state.demo ? '예시 작업실 · 연결 전' : state.mode === 'project' ? '프로젝트 문서 · 읽기 전용' : '로컬 위키';
  $('#source-count').textContent = state.sources?.length || 0;
  $('#example-banner').hidden = !state.demo;
  const defaultModel=boundedText(state.chatDefaultModel,120);
  const modelLabel=defaultModel === 'Pi default' ? '' : defaultModel.split('/').at(-1).replace(/^gpt-/,'GPT-');
  $('#pi-status').textContent = state.piAvailable ? modelLabel ? `기본 · ${modelLabel}` : '사용 가능 · 전송 시 실행' : '설정 확인 필요';
  $('#chat-model').placeholder = modelLabel ? `${modelLabel} · Pi 기본` : 'Pi 기본 모델';
  $('#chat-model').setAttribute('title',defaultModel);
  $('#pi-dot').classList.toggle('ready', Boolean(state.piAvailable));
  renderRetrievalStatus();
  if (!selected || !state.sources?.some(source => source.id === selected)) selected = state.sources?.find(source => source.stage === 'writing')?.id || state.sources?.[0]?.id || null;
  if (!selectedPage || !state.graph?.nodes?.some(node => node.id === selectedPage)) selectedPage = state.graph?.nodes?.[0]?.id || null;
  renderChat(); renderHistory(); renderReferences(); renderKnowledgeGraph();
  renderStats(); renderRun(); renderAutomation(); renderBoard(); renderGraph(); renderDetail(); renderActivity(); renderLibrary(); applyView();
  const warnings = state.warnings || [];
  if (warnings.length) { $('#error-banner').textContent = warnings.join(' · '); $('#error-banner').hidden = false; }
}
function renderStats() {
  if (isProject()) { renderProjectStats(); return; }
  const sources=state.sources||[],done=sources.filter(source=>source.stage==='done').length,active=sources.filter(source=>['reading','writing','review'].includes(source.stage)).length,blocked=sources.filter(source=>source.stage==='blocked').length,total=sources.length,ratio=total?Math.round(done/total*100):0;
  const stat=(label,value,unit,symbol,foot,bar='')=>`<div class="stat"><div class="stat-top">${label}<span class="stat-icon">${icon(symbol)}</span></div><div class="stat-value">${value}<small>${unit}</small></div>${bar||`<div class="stat-foot">${foot}</div>`}</div>`;
  $('#stats').innerHTML=stat('등록된 원문',total,'개','files',`${total-done}개 원문이 완료 전이에요`)+stat('위키 페이지',state.graph.nodes.length,'개','book',`${state.graph.edges.length}개 실제 문서 링크`)+stat('진행 중',active,'개','clock',blocked?`${blocked}개 확인 필요`:'기록에서 확인한 단계')+stat('검증 완료',done,`/ ${total}`,'check','',`<div class="stat-progress" role="progressbar" aria-valuenow="${ratio}" aria-valuemin="0" aria-valuemax="100"><span style="width:${ratio}%"></span></div><div class="stat-foot">${ratio}% 완료 · 시간은 추정하지 않음</div>`);
}
function renderProjectStats() {
  const nodes=state.graph.nodes,wiki=nodes.filter(node=>node.id.startsWith('wiki/')),docs=nodes.filter(node=>node.id.startsWith('docs/')),skills=nodes.filter(node=>node.id.startsWith('.agents/'));
  const stat=(label,value,symbol,foot)=>`<div class="stat"><div class="stat-top">${label}<span class="stat-icon">${icon(symbol)}</span></div><div class="stat-value">${value}<small>개</small></div><div class="stat-foot">${foot}</div></div>`;
  $('#stats').innerHTML=stat('프로젝트 위키',wiki.length,'book','결정과 프로젝트 기록')+stat('프로젝트 문서',docs.length,'files','구조와 검증 근거')+stat('스킬 문서',skills.length,'layout','사용법과 참고 문서')+stat('실제 문서 연결',state.graph.edges.length,'network',`총 ${nodes.length}개 문서`);
}
function renderRun() {
  if (isProject()) { $('#run-strip').innerHTML=`<span class="run-orb">${icon('network')}</span><div class="run-copy"><strong>${escapeHTML(state.name)} 문서 탐색<span class="run-pill">PROJECT WIKI · READ ONLY</span></strong><p>읽기 전용 대화와 문서 탐색을 사용할 수 있습니다. 실행과 업로드는 비활성화됩니다.</p></div><button class="button" data-action="open-index">프로젝트 색인 열기</button>`; return; }
  const job=state.job,parallel=parallelJob(),labels={running:'에이전트가 작업하고 있어요',starting:'작업을 준비하고 있어요',stopping:'안전하게 중단하는 중',stopped:'작업이 중단되었어요',finished:'에이전트 실행이 끝났어요',failed:'실행을 확인해 주세요',interrupted:'이전 작업의 연결이 끊겼어요',external:'다른 실행 서비스에서 작업 중이에요'},phase={planning:'계획 중',preparing:'병렬 초안 준비 중',needs_attention:'병렬 작업 확인 필요',prepared:'초안 준비 완료 · 통합 대기',stopped:'병렬 준비 중단'};
  const workers=Array.isArray(parallel?.workers)?parallel.workers:[],preparedCount=workers.filter(worker=>worker.status==='prepared').length,activeCount=workers.filter(worker=>['reading','drafting'].includes(worker.status)).length,workerTotal=workers.length;
  const heading=state.demo?'원문 처리 흐름을 살펴보세요':job?labels[job.status]||'실행 기록':'위키 작업을 시작할 준비가 됐어요',description=state.demo?'실제 실행이 아닌 예시입니다.':parallel?parallel.error||(allRequestedSourcesVerified(job)?`초안 준비 기록됨 · 현재 원문 검증 완료 · 초안 준비 ${preparedCount}/${workerTotal} · 동시 실행 ${activeCount}/${parallel.parallelism||workerTotal}`:`${phase[parallel.phase]||parallel.phase} · 초안 준비 ${preparedCount}/${workerTotal} · 동시 실행 ${activeCount}/${parallel.parallelism||workerTotal}`):job?job.events?.at(-1)?.detail||job.message:'자료 추가와 위키 만들기는 대화와 별개의 쓰기 작업입니다.';
  $('#run-strip').innerHTML=`<span class="run-orb">${icon('spark')}</span><div class="run-copy"><strong>${escapeHTML(heading)}<span class="run-pill">${state.demo?'PREVIEW':isRunning()?'RUNNING':'PI'}</span></strong><p>${escapeHTML(description)}</p></div>${isRunning()?`<button class="button" data-action="steer">추가 지시</button><button class="button" data-action="stop" ${job.status==='stopping'?'disabled':''}>전체 작업 중단</button>`:''}${parallel?.canResumeIntegration===true&&!isRunning()?`<button class="button primary" data-action="resume-integration">통합 재개</button>`:''}`;
}
function automationReason() {
  if (state?.demo) return '예시 작업실에서는 폴더 감시를 설정하지 않습니다. 내 위키를 연결하세요.';
  if (isProject()) return '프로젝트는 읽기 전용이라 폴더 감시와 파일 변경을 사용할 수 없습니다.';
  if (state?.automation?.available === false || !state?.automation) return '현재 서버에서 폴더 감시 기능을 제공하지 않습니다. 서버를 업데이트하고 다시 연결하세요.';
  return '';
}
function captureWatchDraft(form=$('#watch-config-form')) {
  if(!form)return null;
  watchDraft={root:currentRoot(),dirty:true,enabled:Boolean($('[name="enabled"]',form)?.checked),autoRun:Boolean($('[name="autoRun"]',form)?.checked),sourcePath:String($('[name="sourcePath"]',form)?.value||''),includeExisting:Boolean($('[name="includeExisting"]',form)?.checked)};
  return watchDraft;
}
function watchFocusSnapshot() {
  const active=document.activeElement,name=active?.name;
  if(!['sourcePath','enabled','autoRun','includeExisting'].includes(name)||!active.closest?.('#watch-config-form'))return null;
  return {name,start:Number.isInteger(active.selectionStart)?active.selectionStart:null,end:Number.isInteger(active.selectionEnd)?active.selectionEnd:null};
}
function restoreWatchFocus(snapshot) {
  if(!snapshot)return;const input=$(`[name="${snapshot.name}"]`,$('#watch-config-form'));if(!input)return;input.focus?.();if(snapshot.start!==null&&input.setSelectionRange)input.setSelectionRange(snapshot.start,snapshot.end);
}
function renderAutomation() {
  const focus=watchFocusSnapshot(),automation=state?.automation||{},queue=Array.isArray(automation.queue)?automation.queue:[],reason=automationReason(),disabled=Boolean(reason)||watchSubmitting;
  const draft=watchDraft?.dirty&&watchDraft.root===currentRoot()?watchDraft:null;
  const computed={pending:queue.filter(item=>item.status==='pending').length,running:queue.filter(item=>item.status==='running').length,completed:queue.filter(item=>item.status==='completed').length,needsAttention:queue.filter(item=>item.status==='needs_attention').length};
  const counts={...computed,...(automation.counts||{})},page=queuePageInfo(automation.queuePage,queue.length),rangeStart=page.total?page.offset+1:0,rangeEnd=Math.min(page.total,page.offset+queue.length),hasPrevious=page.offset>0,hasNext=page.offset+page.limit<page.total;
  $('#watch-count').textContent=String((counts.pending||0)+(counts.running||0)+(counts.needsAttention||0));
  const defaultPath=automation.sourcePath || (state?.root?`${String(state.root).replace(/\/$/,'')}/raw`:'root/raw');
  const formValues=draft||{enabled:Boolean(automation.enabled),autoRun:Boolean(automation.autoRun),sourcePath:defaultPath,includeExisting:false};
  const status=automation.enabled?(automation.autoRun?'켜짐 · 변경 감지 후 자동 실행':'켜짐 · 변경 감지만'):'꺼짐 · 기본값';
  const rows=queue.length?queue.map(item=>{
    const targets=queueTargets(item),canRun=['pending','needs_attention'].includes(item.status),canIgnore=['pending','needs_attention'].includes(item.status);
    return `<article class="queue-card ${escapeHTML(item.status)}"><div class="queue-card-main"><div class="queue-title"><span class="file-badge">MD</span><strong>${escapeHTML(item.title||item.source||'이름 없는 원문')}</strong></div><div class="queue-meta"><span>${escapeHTML(item.origin==='conversation'?'대화 저장':changeLabels[item.change]||item.change||item.origin||'변경')}</span><span class="queue-status">${escapeHTML(queueLabels[item.status]||item.status)}</span><span>${escapeHTML(formatElapsed(item))}</span>${item.jobId?`<span>작업 ${escapeHTML(item.jobId)}</span>`:''}</div>${item.source?`<button class="queue-source" data-page="${escapeHTML(item.source)}">${escapeHTML(item.source)}</button>`:''}${item.reason?`<p class="queue-reason">${escapeHTML(item.reason)}</p>`:''}${targets.length?`<div class="queue-targets"><span>실제 반영 대상</span>${targets.map(target=>`<button data-page="${escapeHTML(target.id)}">${escapeHTML(target.title||target.id)}</button>`).join('')}</div>`:''}</div><div class="queue-actions">${canRun?`<button data-watch-run="${escapeHTML(item.id)}">${item.status==='needs_attention'?'재시도':'실행'}</button>`:''}${canIgnore?`<button data-watch-ignore="${escapeHTML(item.id)}">제외</button>`:''}</div></article>`;
  }).join(''):'<div class="automation-empty">감지된 Markdown 변경이 없습니다. 설정을 적용해도 기존 파일은 별도로 선택하지 않는 한 추가하지 않습니다.</div>';
  $('#automation-panel').innerHTML=`<div class="automation-heading"><div><span class="eyebrow">FOLDER WATCH</span><h2>폴더 감시</h2><p>기본은 OFF입니다. 감지만 켜면 대기열에 쌓이고, 자동 실행은 별도 동의가 필요합니다.</p></div><span class="automation-state ${automation.enabled?'on':''}">${escapeHTML(status)}${draft?' · 입력 변경 적용 전':''}</span></div><form id="watch-config-form" class="watch-config"><label class="field compact-field">감시할 원문 폴더<input name="sourcePath" value="${escapeHTML(formValues.sourcePath)}" ${disabled?'disabled':''} autocomplete="off"></label><div class="watch-options"><label><input type="checkbox" name="enabled" ${formValues.enabled?'checked':''} ${disabled?'disabled':''}>폴더 감시 켜기 <small>변경 감지와 수동 실행</small></label><label><input type="checkbox" name="autoRun" ${formValues.autoRun?'checked':''} ${disabled?'disabled':''}>자동 실행 허용 <small>선택한 모델을 사용해 위키 파일을 변경할 수 있음</small></label><label><input type="checkbox" name="includeExisting" ${formValues.includeExisting?'checked':''} ${disabled?'disabled':''}>기존 파일도 처음 한 번 감지 <small>기본 선택 안 함</small></label></div><div class="watch-form-footer"><p>${reason?escapeHTML(reason):'대시보드 서버가 실행 중이고 현재 연결한 워크스페이스에서만 작동합니다.'}<br>Markdown만 · 파일당 최대 2MB · 감시 OFF는 새 변경 감지와 자동 실행 시작을 멈춥니다.<br>현재 실행, 명시적 수동 실행, 대화 원문 저장은 취소되지 않습니다.</p><button class="button primary" type="submit" ${disabled?'disabled':''}>${watchSubmitting?'적용 중…':'설정 적용'}</button></div></form><div class="queue-heading"><div><h3>실시간 작업 대기열</h3><span>대기 ${counts.pending||0} · 실행 ${counts.running||0} · 완료 ${counts.completed||0} · 확인 ${counts.needsAttention||0}</span></div><small>${rangeStart}–${rangeEnd} / 전체 ${page.total}개 · 완료 시간은 실제 기록만 표시합니다.</small></div><div class="queue-list">${rows}</div><div class="queue-pagination" aria-label="작업 대기열 페이지"><span>${rangeStart}–${rangeEnd} / ${page.total}</span><div><button data-action="queue-previous" ${hasPrevious?'':'disabled'}>이전</button><button data-action="queue-next" ${hasNext?'':'disabled'}>다음</button></div></div>`;
  restoreWatchFocus(focus);
}
function watchConfigPayload(form=$('#watch-config-form')) {
  return {expectedRoot:currentRoot(),enabled:Boolean($('[name="enabled"]',form)?.checked),autoRun:Boolean($('[name="autoRun"]',form)?.checked),sourcePath:String($('[name="sourcePath"]',form)?.value||'').trim(),includeExisting:Boolean($('[name="includeExisting"]',form)?.checked)};
}
async function applyWatchConfig() {
  const reason=automationReason(); if(reason)throw new Error(reason);
  const body=watchConfigPayload(); if(!body.sourcePath)throw new Error('감시할 원문 폴더를 입력해 주세요.');
  watchDraft={...body,root:body.expectedRoot,dirty:true}; watchSubmitting=true; renderAutomation();
  try { const result=await api('watch-config',body); if(currentRoot()!==body.expectedRoot)throw new Error('워크스페이스가 바뀌어 설정 결과를 적용하지 않았습니다.'); if(result.root&&String(result.root)!==body.expectedRoot)throw new Error('다른 워크스페이스의 설정 결과는 적용하지 않았습니다.'); state.automation=result.automation||result; watchDraft=null; await refresh(true); toast(body.enabled?(body.autoRun?'폴더 감지와 자동 실행을 켰습니다.':'폴더 감지를 켰습니다. 실행은 대기열에서 직접 시작합니다.'):'폴더 감시를 껐습니다.'); }
  finally { watchSubmitting=false; renderAutomation(); }
}
function mergeQueueItem(item) {
  if(!item?.id)return; const queue=state.automation.queue||(state.automation.queue=[]),index=queue.findIndex(value=>String(value.id)===String(item.id)); if(index>=0)queue[index]=item;else queue.unshift(item);
}
async function runWatchItem(id) { const rootAtStart=currentRoot(),item=await api('watch-run',{expectedRoot:rootAtStart,id}); if(currentRoot()!==rootAtStart)return;mergeQueueItem(item);renderAutomation();await refresh(true); }
async function ignoreWatchItem(id) { const rootAtStart=currentRoot(),item=await api('watch-ignore',{expectedRoot:rootAtStart,id}); if(currentRoot()!==rootAtStart)return;mergeQueueItem(item);renderAutomation();await refresh(true); }
async function moveWatchQueuePage(direction) {
  const page=queuePageInfo(state?.automation?.queuePage,state?.automation?.queue?.length||0),target=direction<0?Math.max(0,page.offset-page.limit):Math.min(Math.max(0,page.total-1),page.offset+page.limit);
  if(target===watchQueueOffset)return;watchQueueOffset=target;await refresh(true);
}
function filteredSources() { return (state.sources||[]).filter(source=>(!query||(source.title+' '+source.id).toLowerCase().includes(query.toLowerCase()))&&(!blockedOnly||source.stage==='blocked')); }
function renderBoard() {
  const sources=filteredSources(); $('#board-count').textContent=`${sources.length}개 원문`;
  if (!(state.sources||[]).length) { $('#board').innerHTML=isProject()?'<div class="empty-board"><strong>프로젝트는 읽기 전용입니다.</strong>대화와 문서 탐색에서 실제 프로젝트 문서를 확인하세요.</div>':'<div class="empty-board"><strong>첫 번째 원문을 추가해 보세요.</strong>Markdown 자료를 추가한 뒤 위키 만들기에서 작업을 시작할 수 있습니다.</div>'; return; }
  if (!sources.length) { $('#board').innerHTML='<div class="empty-board">조건에 맞는 원문이 없습니다. 검색어나 필터를 바꿔 보세요.</div>'; return; }
  const columns=blockedOnly?[['blocked','확인 필요','#b8792e']]:stages;
  $('#board').innerHTML=columns.map(([key,label,color])=>{const group=sources.filter(source=>sourceOperationStage(source)===key||(key==='review'&&sourceOperationStage(source)==='blocked'));return `<div class="column ${key}" style="--column-color:${color}"><div class="column-head"><i></i>${label}<span>${group.length}</span></div>${group.map(source=>{const coverage=source.coverage?.valid?source.coverage:null,percent=coverage?Math.round((coverage.projected+coverage.omitted)/coverage.total*100):null,worker=parallelWorker(source.id),operating=parallelActive()&&workerOperationStage(worker);return `<button class="column-card ${selected===source.id?'selected':''} ${operating?'worker-active':''}" data-source="${escapeHTML(source.id)}" aria-pressed="${selected===source.id}"><span class="file-badge">MD</span><strong class="card-title">${escapeHTML(source.title)}</strong><div class="card-description">${escapeHTML(source.id.split('/').at(-1))}</div>${workerBadge(worker,source)}${percent!==null?`<div class="card-progress"><i style="width:${percent}%"></i></div>`:''}<div class="card-footer"><span>${operating?(source.stage==='done'?'기존 검증 완료':`위키 상태: ${escapeHTML(phaseLabels[source.stage]||source.stage)}`):escapeHTML(certifiedSourceLabel(source))}</span><span>${coverage?`${coverage.projected+coverage.omitted}/${coverage.total}`:'범위 확인 전'}</span></div></button>`;}).join('')||'<div class="column-empty">이 단계의 원문이 없어요</div>'}</div>`;}).join('');
}
function relatedIds() { if (isProject()) return new Set([selectedPage,...state.graph.edges.flatMap(edge=>edge.source===selectedPage?[edge.target]:edge.target===selectedPage?[edge.source]:[])]); return new Set(currentSource()?.references||[]); }
function renderGraph() {
  const related=relatedIds(); let nodes=state.graph.nodes.filter(node=>(!query||(node.title+' '+node.id).toLowerCase().includes(query.toLowerCase()))&&(graphMode!=='related'||related.has(node.id))); const total=nodes.length; nodes=nodes.slice(0,GRAPH_LIMIT); const ids=new Set(nodes.map(node=>node.id)),edges=state.graph.edges.filter(edge=>ids.has(edge.source)&&ids.has(edge.target));
  $('#graph-count').textContent=`${nodes.length}개 페이지`; $('#graph-scope').textContent=total>GRAPH_LIMIT?`전체 ${total}개 중 ${GRAPH_LIMIT}개 표시`:'실제 문서 링크 기반';
  if (!nodes.length) { $('#graph-canvas').innerHTML='<div class="graph-empty">연결된 문서가 없습니다.</div>'; return; }
  const width=isProject()?960:680,height=isProject()?480:290,layout=positions(nodes,edges,width,height),degree=new Map(); edges.forEach(edge=>[edge.source,edge.target].forEach(id=>degree.set(id,(degree.get(id)||0)+1)));
  $('#graph-canvas').innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="문서 링크 그래프"><g class="graph-viewport" transform="translate(${width/2} ${height/2}) scale(${zoom}) translate(${-width/2} ${-height/2})">${edges.map(edge=>{const a=layout.get(edge.source),b=layout.get(edge.target);return `<line class="graph-edge ${related.has(edge.source)||related.has(edge.target)?'related':''}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;}).join('')}${nodes.map(node=>{const point=layout.get(node.id),isRelated=related.has(node.id),radius=Math.min(10,5+(degree.get(node.id)||0));return `<g class="graph-node ${isRelated?'related-node':''}" data-page="${escapeHTML(node.id)}" role="button" tabindex="0" aria-label="${escapeHTML(node.title)} 열기" transform="translate(${point.x} ${point.y})">${isRelated?`<circle class="node-ring" r="${radius+5}"/>`:''}<circle class="node-core" r="${radius}"/><title>${escapeHTML(node.title)}</title><text y="${radius+18}">${escapeHTML(node.title.length>17?node.title.slice(0,16)+'…':node.title)}</text></g>`;}).join('')}</g></svg>`; $('#zoom-label').textContent=`${Math.round(zoom*100)}%`;
}
function renderDetail() {
  if (isProject()) { renderProjectDetail(); return; }
  const source=currentSource(); if (!source) { $('#detail-panel').innerHTML='<div class="detail-top"><span class="eyebrow">SOURCE INSPECTOR</span><h3>원문을 선택해 주세요</h3></div><div class="detail-content"><p class="coverage-note">카드를 선택하면 실제 절차 기록과 연결된 문서를 보여줍니다.</p></div>'; return; }
  const coverage=source.coverage?.valid?source.coverage:null,done=new Set(source.run?.completed_stages||[]),percent=coverage?Math.round((coverage.projected+coverage.omitted)/coverage.total*100):null,groups=[['읽기 · 범위 확인',procedure.slice(0,2)],['합성 계획 확정',procedure.slice(2,3)],['위키 반영',procedure.slice(3,7)],['구조 검증',procedure.slice(7,8)],['최종 검토 · 완료',procedure.slice(8)]]; let first=true;
  const steps=groups.map(([label,keys])=>{const failed=label==='구조 검증'&&(source.run?.blockers||[]).includes('STRUCTURAL_VALIDATION_FAILED'),complete=!failed&&keys.every(key=>done.has(key))&&(label!=='최종 검토 · 완료'||source.stage==='done'),active=!complete&&first;if(active)first=false;return `<div class="step ${complete?'complete':active?'current':''}"><span class="step-dot">${complete?'✓':active?'•':''}</span>${label}<small>${failed?'실패':complete?'확인됨':active?'다음 단계':'대기'}</small></div>`;}).join('');
  const refs=(source.references||[]).filter(ref=>!ref.startsWith('wiki/_meta/')),blockers=(source.run?.blockers||[]).filter(blocker=>blocker!=='PROCEDURE_STAGE_MISSING');
  const worker=parallelWorker(source.id),workerInfo=worker?`<div class="worker-detail"><strong>${escapeHTML(workerLabel(worker,source))}</strong>${worker.error?`<span>${escapeHTML(worker.error)}</span>`:''}<small>시도 ${escapeHTML(worker.attempt||0)} · 읽기 ${escapeHTML(worker.readCount||0)}회</small>${worker.canStop?`<button data-worker-stop="${escapeHTML(source.id)}">이 원문 중단</button>`:''}${worker.canRetry?`<button data-worker-retry="${escapeHTML(source.id)}">재시도</button>`:''}</div>`:'';
  $('#detail-panel').innerHTML=`<div class="detail-top"><span class="eyebrow">SOURCE INSPECTOR</span><h3>${escapeHTML(source.title)}</h3><div class="detail-path">${escapeHTML(source.id)}</div></div><div class="detail-content"><div class="coverage-line"><span>원문 내용 처리</span><strong>${percent===null?'범위 확인 전':percent+'%'}</strong></div><div class="coverage-track">${coverage?`<i style="width:${coverage.projected/coverage.total*100}%"></i><i class="omitted" style="width:${coverage.omitted/coverage.total*100}%"></i>`:''}</div><div class="coverage-note">${coverage?`반영 ${coverage.projected} · 사유 있는 제외 ${coverage.omitted} · 보류 ${coverage.deferred}<br>전체 ${coverage.total}개 구간 · 검증 완료와 별도 집계`:source.coverage?'반영 기록이 현재 원문과 일치하지 않아 집계를 표시하지 않습니다.':'확정된 반영 기록이 생기면 처리량을 표시합니다.'}</div><div class="steps">${steps}</div>${workerInfo}${blockers.length?`<div class="blocker-note">${blockers.map(blocker=>escapeHTML(niceBlocker[blocker]||blocker)).join('<br>')}</div>`:''}<div class="related-title">연결된 위키 ${refs.length}</div><div class="related-links">${refs.slice(0,6).map(ref=>`<button data-page="${escapeHTML(ref)}">${escapeHTML(graphNodeTitle(ref))}</button>`).join('')||'<span class="muted">아직 반영된 페이지가 없어요</span>'}</div></div><div class="detail-footer"><span>${phaseLabels[source.stage]}</span><button class="text-button" data-page="${escapeHTML(source.id)}">원문 보기</button></div>`;
}
function renderProjectDetail() {
  const page=state.graph.nodes.find(node=>node.id===selectedPage)||state.graph.nodes[0]; if(!page){$('#detail-panel').innerHTML='<div class="detail-content">표시할 프로젝트 문서가 없습니다.</div>';return;} const outgoing=state.graph.edges.filter(edge=>edge.source===page.id),incoming=state.graph.edges.filter(edge=>edge.target===page.id),link=id=>`<button data-select-page="${escapeHTML(id)}">${escapeHTML(graphNodeTitle(id))}</button>`;
  $('#detail-panel').innerHTML=`<div class="detail-top"><span class="eyebrow">PROJECT INSPECTOR</span><h3>${escapeHTML(page.title)}</h3><div class="detail-path">${escapeHTML(page.id)}</div></div><div class="detail-content"><div class="coverage-line"><span>문서의 실제 연결</span><strong>${incoming.length+outgoing.length}개</strong></div><p class="coverage-note">읽기 전용 프로젝트 문서입니다.</p><div class="related-title">이 문서가 참조하는 문서 ${outgoing.length}</div><div class="related-links">${outgoing.map(edge=>link(edge.target)).join('')||'<span class="muted">연결된 문서 없음</span>'}</div><div class="related-title">이 문서를 참조하는 문서 ${incoming.length}</div><div class="related-links">${incoming.map(edge=>link(edge.source)).join('')||'<span class="muted">참조하는 문서 없음</span>'}</div></div><div class="detail-footer"><span>실제 프로젝트 파일</span><button class="text-button" data-page="${escapeHTML(page.id)}">문서 읽기</button></div>`;
}
function renderLibrary() {
  const nodes=state.graph.nodes.filter(node=>!query||(node.title+' '+node.id).toLowerCase().includes(query.toLowerCase()));
  $('#document-library').innerHTML=`<div class="library-heading"><h2>문서 전체</h2><span class="muted">${nodes.length}개 · 선택하면 본문이 열립니다</span></div><div class="document-grid">${nodes.map(node=>`<button class="document-card" data-page="${escapeHTML(node.id)}"><span class="document-category">${node.id.startsWith('wiki/')?'WIKI':node.id.startsWith('raw/')?'RAW':node.id.startsWith('.agents/')?'SKILL':'DOC'}</span><strong>${escapeHTML(node.title)}</strong><span class="document-card-path">${escapeHTML(node.id)}</span></button>`).join('')||'<p class="coverage-note">검색 결과가 없습니다.</p>'}</div>`;
}
function renderActivity() {
  if (isProject()) { $('#activity-panel').innerHTML=`<div class="section-heading">${icon('activity')}<h2>최근 수정된 문서</h2></div>${[...state.graph.nodes].sort((a,b)=>b.modified-a.modified).slice(0,20).map(node=>`<div class="activity-row"><time>${new Date(node.modified*1000).toLocaleDateString('ko-KR')}</time><div><button class="text-button" data-page="${escapeHTML(node.id)}">${escapeHTML(node.title)}</button><p>${escapeHTML(node.id)}</p></div></div>`).join('')}`; return; }
  const events=state.job?.events||[]; $('#activity-panel').innerHTML=`<div class="section-heading">${icon('activity')}<h2>실행 기록</h2></div>${events.length?events.slice().reverse().map(event=>`<div class="activity-row"><time>${new Date(event.time*1000).toLocaleTimeString('ko-KR',{hour12:false})}</time><div><strong>${escapeHTML(event.label)}</strong><p>${escapeHTML(event.detail)}</p></div></div>`).join(''):'<div class="coverage-note">아직 실행 기록이 없습니다.</div>'}`;
}
function applyView() {
  const chat=view==='chat',watch=view==='watch';
  $('#chat-view').hidden=!chat; $('#work-view').hidden=chat; $('#breadcrumb').textContent={chat:'대화',work:'위키 작업',watch:'폴더 감시',library:'문서',activity:'기록'}[view]||'대화';
  $$('.nav-item').forEach(button=>{const active=button.dataset.view===view;button.classList.toggle('active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  if (!chat) {
    $('#page-title').textContent=watch?'폴더 감시':'위키 작업'; $('#page-subtitle').textContent=watch?'Markdown 변경을 감지하고 명시적으로 위키 정리를 시작합니다.':'원문 처리와 검증 기록을 관리합니다.';
    $('#surface-title').textContent=watch?'기존 원문 품질 보드':'원문 작업 보드'; $('#automation-panel').hidden=!watch;
    $('#board').hidden=!['work','watch'].includes(view)||isProject(); $('#lower-grid').hidden=view==='library'||view==='activity'; $('#document-library').hidden=view!=='library'; $('#activity-panel').hidden=view!=='activity';
    $('.workspace-toolbar').hidden=view==='activity'; $('.heading-actions').hidden=isProject(); $('#blocked-filter').hidden=isProject()||!['work','watch'].includes(view); $('#board-count').hidden=isProject()||!['work','watch'].includes(view);
  }
  document.body.classList.toggle('project-mode',isProject());
}

function setFolderPickerPending(pending) {
  folderPickerPending = pending;
  $('#choose-folder').disabled = pending;
  $('#folder-picker-status').hidden = !pending;
  $('[type=submit]',$('#connect-form')).disabled = pending;
}
function invalidateFolderPicker() {
  folderPickerGeneration += 1;
  if (folderPickerPending) setFolderPickerPending(false);
}
function setFolderBrowserPending(pending) {
  folderBrowserPending=pending;
  $('#folder-browser-up').disabled=pending||!folderBrowserLocation?.parent;
  $('#folder-browser-select').disabled=pending||!folderBrowserLocation?.path;
  $('#folder-browser-status').textContent=pending?'폴더를 불러오는 중…':'';
}
function invalidateFolderBrowser({close=false}={}) {
  folderBrowserGeneration+=1;
  folderBrowserContext=null;
  if(folderBrowserPending)setFolderBrowserPending(false);
  if(close&&$('#folder-browser-dialog').open)$('#folder-browser-dialog').close();
}
function browserIsCurrent(request, context) {
  return request===folderBrowserGeneration && $('#folder-browser-dialog').open && $('#connect-dialog').open && folderBrowserContext===context && $('#connect-root').value===context.rootAtStart && state?.root===context.workspaceAtStart;
}
function browserLocation(result) {
  const string=value=>typeof value==='string'&&value.length?value:null;
  return {
    path:string(result?.path), parent:string(result?.parent),
    directories:Array.isArray(result?.directories)?result.directories.filter(item=>string(item?.name)&&string(item?.path)).map(item=>({name:item.name,path:item.path})):[],
    shortcuts:Array.isArray(result?.shortcuts)?result.shortcuts.filter(item=>string(item?.name)&&string(item?.path)).map(item=>({name:item.name,path:item.path})):[],
    truncated:result?.truncated===true
  };
}
function renderFolderBrowser(location) {
  folderBrowserLocation=location;
  $('#folder-browser-path').textContent=location.path||'현재 폴더를 확인하지 못했습니다.';
  $('#folder-browser-up').disabled=!location.parent;
  $('#folder-browser-shortcuts').innerHTML=location.shortcuts.map(item=>`<button type="button" data-action="folder-browser-go" data-path="${escapeHTML(item.path)}">${escapeHTML(({Home:'홈','Current wiki':'현재 위키','Filesystem root':'컴퓨터',Volumes:'외장 드라이브'})[item.name]||item.name)}</button>`).join('');
  $('#folder-browser-list').innerHTML=location.directories.length?location.directories.map(item=>`<button type="button" data-action="folder-browser-go" data-path="${escapeHTML(item.path)}">${escapeHTML(item.name)}</button>`).join(''):'<div class="folder-browser-empty">이 폴더 안에 표시할 하위 폴더가 없습니다.</div>';
  $('#folder-browser-truncated').hidden=!location.truncated;
  setFolderBrowserPending(false);
}
async function browseFolders(path) {
  const dialog=$('#folder-browser-dialog');
  const context=folderBrowserContext;
  if(!context||folderBrowserPending)return;
  const request=++folderBrowserGeneration;
  setFolderBrowserPending(true);
  $('#folder-browser-error').textContent='';
  try {
    const result=await api('browse-folders',path?{path}:{});
    if(!browserIsCurrent(request,context))return;
    const location=browserLocation(result);
    if(!location.path)throw new Error('폴더 위치를 확인하지 못했습니다. 경로를 직접 입력해 주세요.');
    renderFolderBrowser(location);
  } catch(error) {
    if(!browserIsCurrent(request,context))return;
    folderBrowserLocation=null;
    $('#folder-browser-list').innerHTML='<div class="folder-browser-empty">폴더를 불러오지 못했습니다. 직접 경로를 입력해 연결할 수 있습니다.</div>';
    $('#folder-browser-error').textContent=error?.message||'작업실에서 폴더를 불러오지 못했습니다.';
  } finally {
    if(request===folderBrowserGeneration)setFolderBrowserPending(false);
  }
}
function openFolderBrowser() {
  const connect=$('#connect-dialog');
  if(!connect.open)return;
  invalidateFolderPicker();
  const browser=$('#folder-browser-dialog');
  folderBrowserLocation=null;
  folderBrowserContext={rootAtStart:$('#connect-root').value,workspaceAtStart:state?.root};
  $('#folder-browser-error').textContent=''; $('#folder-browser-path').textContent='폴더 위치를 불러오는 중…'; $('#folder-browser-shortcuts').innerHTML=''; $('#folder-browser-list').innerHTML=''; $('#folder-browser-truncated').hidden=true;
  if(!browser.open)browser.showModal();
  browseFolders();
}
function selectFolderBrowser() {
  const context=folderBrowserContext, location=folderBrowserLocation;
  if(!context||!location?.path||folderBrowserPending||!browserIsCurrent(folderBrowserGeneration,context))return;
  $('#connect-root').value=location.path;
  invalidateFolderBrowser({close:true});
}
async function chooseFolder() {
  if (folderPickerPending) return;
  const dialog=$('#connect-dialog');
  const form=$('#connect-form');
  const input=$('#connect-root');
  const request=++folderPickerGeneration;
  const rootAtStart=input.value;
  const workspaceAtStart=state?.root;
  const isCurrent=()=>request===folderPickerGeneration && dialog.open && input.value===rootAtStart && state?.root===workspaceAtStart;
  setFolderPickerPending(true);
  $('.form-error',form).textContent='';
  $('#folder-picker-note').hidden=true;
  try {
    const result=await api('choose-folder',{});
    if (!isCurrent()) return;
    if (result?.cancelled) return;
    const root=result?.root;
    if (typeof root!=='string' || !root.trim()) throw new Error('선택한 폴더를 확인하지 못했습니다.');
    input.value=root;
  } catch (error) {
    if (!isCurrent()) return;
    $('#folder-picker-note').textContent='OS 창 대신 작업실에서 폴더를 선택하세요.';
    $('#folder-picker-note').hidden=false;
    setFolderPickerPending(false);
    openFolderBrowser();
  } finally {
    if (request===folderPickerGeneration) setFolderPickerPending(false);
  }
}
function openDialog(id) { const element=$(id); if(id==='#connect-dialog')invalidateFolderPicker(); const error=$('.form-error',element); if(error)error.textContent=''; element.showModal(); }
function openTask(mode='start') {
  if(!state)return; if(state.demo){openDialog('#connect-dialog');return;} if(isProject()){toast('프로젝트 문서는 읽기 전용입니다. 대화는 그대로 사용할 수 있습니다.');return;} if(mode==='start'&&isRunning()){toast('작업 중입니다. 추가 지시를 이용하세요.');return;} if(!state.piAvailable){toast('Pi 설정을 확인한 뒤 다시 시도하세요.');return;}
  taskMode=mode; $('#task-title').textContent=mode==='steer'?'추가 지시 보내기':'위키 만들기'; $('#task-source-field').hidden=mode==='steer'; $('#parallelism-field').hidden=!parallelPreparationAvailable(); $('#task-submit').textContent=mode==='steer'?'추가 지시 보내기':'선택한 자료로 시작'; $('#task-form textarea').value=mode==='steer'?'':'선택한 원문을 빠짐없이 반영해 위키를 만들고, 근거와 검증 결과를 남겨줘. 기존 작업이 있으면 상태를 확인하고 이어서 진행해줘.'; $('#task-sources').innerHTML=state.sources.map(source=>`<label class="task-source"><input type="checkbox" name="source" value="${escapeHTML(source.id)}" ${source.id===selected?'checked':''}><span>${escapeHTML(source.title)} <span class="muted">· ${phaseLabels[source.stage]}</span></span></label>`).join('')||'<p class="field-note">먼저 Markdown 자료를 추가해 주세요.</p>'; openDialog('#task-dialog');
}
function resetDocumentReader() {
  documentRequest+=1;
  documentLinks.clear();
  const dialog=$('#document-dialog');
  if (dialog.open) dialog.close();
  $('#document-title').textContent='문서'; $('#document-path').textContent=''; $('#document-kind').textContent='WIKI DOCUMENT';
  $('#document-relations').innerHTML=''; $('#document-body').textContent='';
}
async function openPage(path, {expectedContentHash='',citation=false} = {}) {
  $('#document-scroll').scrollTop=0;
  const request=++documentRequest,rootAtStart=String(state?.root||''),expectedHash=normalizeContentHash(expectedContentHash);
  const fallbackTitle=graphNodeTitle(path); $('#document-title').textContent=fallbackTitle; $('#document-path').textContent=path; $('#document-kind').textContent=path.startsWith('raw/')?'RAW SOURCE':'WIKI DOCUMENT'; $('#document-relations').innerHTML=''; $('#document-body').textContent='문서를 읽고 있어요…'; if(!$('#document-dialog').open)openDialog('#document-dialog');
  try {
    let data;
    if(state.demo) data={path,title:fallbackTitle,text:state.documents?.[path]||'# 예시 페이지\n\n실제 위키를 연결하면 문서 본문이 표시됩니다.',rawSources:[],links:[]};
    else data=await api('document?path='+encodeURIComponent(path)+'&expectedRoot='+encodeURIComponent(rootAtStart));
    if(request!==documentRequest||String(state?.root||'')!==rootAtStart)return;
    const currentHash=normalizeContentHash(data.contentHash);
    if (expectedHash && currentHash!==expectedHash) {
      $('#document-kind').textContent='CITATION SNAPSHOT MISMATCH';
      $('#document-body').textContent='인용 당시 읽은 문서와 현재 문서의 내용 해시가 다르거나 현재 해시를 확인할 수 없습니다. 현재 문서를 오래된 인용의 근거로 표시하지 않았습니다.';
      return;
    }
    const text=String(data.text ?? data.content ?? '');
    const rawSources=Array.isArray(data.rawSources)?data.rawSources.filter(item=>item?.id):[];
    const links=Array.isArray(data.links)?data.links.filter(item=>item?.id):[];
    documentLinks=new Set([...rawSources,...links].map(item=>String(item.id)));
    $('#document-title').textContent=String(data.title||fallbackTitle);
    $('#document-relations').innerHTML=`${citation&&!expectedHash?'<section><span>이전 대화 인용에는 당시 문서 해시가 없어 현재 문서와 비교할 수 없습니다.</span></section>':''}${rawSources.length?`<section><span>연결된 원문</span>${rawSources.map(raw=>`<button data-page="${escapeHTML(raw.id)}">${escapeHTML(raw.title||raw.id)}</button>`).join('')}</section>`:''}${links.length?`<section><span>문서 연결</span>${links.map(link=>`<button data-page="${escapeHTML(link.id)}">${escapeHTML(link.title||link.id)}${link.kind?` <small>${escapeHTML(link.kind)}</small>`:''}</button>`).join('')}</section>`:''}`;
    $('#document-body').innerHTML=renderMarkdown(text,path,normalizeReferences(rawSources));
  } catch(error) { if(request===documentRequest&&String(state?.root||'')===rootAtStart)$('#document-body').textContent=error.message; }
}
function openReferenceById(id, references = null) {
  const pool=references||referencesForActiveAnswer();
  const reference=pool.find(item=>item.id===id); if(!reference)return false; openPage(reference.id,{expectedContentHash:reference.contentHash,citation:true}); return true;
}
function openCitationReference(id, answerIndex = null, provisional = false) {
  if (Number.isInteger(answerIndex)) focusAnswer(answerIndex);
  const references=provisional?(activeChatJob?.references||[]):referencesForActiveAnswer();
  return openReferenceById(id,references);
}
function toggleKnowledge() {
  const open=!document.body.classList.contains('knowledge-open'); document.body.classList.toggle('knowledge-open',open); $('.knowledge-backdrop').hidden=!open; $('.mobile-knowledge-button').setAttribute('aria-expanded',String(open));
}

async function controlParallelWorker(source, action) { const rootAtStart=currentRoot(),jobId=state?.job?.id; if(!jobId)throw new Error('현재 작업을 찾지 못했습니다.'); const body={expectedRoot:rootAtStart,jobId,source}; await api(action==='stop'?'batch-worker-stop':'batch-worker-retry',body); if(currentRoot()!==rootAtStart||state?.job?.id!==jobId)return; await refresh(true); }
async function resumeParallelIntegration() { const rootAtStart=currentRoot(),jobId=state?.job?.id; if(!jobId)throw new Error('현재 작업을 찾지 못했습니다.'); await api('batch-resume',{expectedRoot:rootAtStart,jobId}); if(currentRoot()!==rootAtStart||state?.job?.id!==jobId)return; await refresh(true); }
function handleClick(event) {
  // Let native disclosure toggles run without replacing their enclosing answer.
  if (event.target.closest?.('summary')) return;
  const target=event.target.closest?.('button,a,[data-page],[data-answer-index]'); if(!target)return;
  if(target.hasAttribute('data-close')){const dialog=target.closest('dialog');dialog.close();if(dialog.id==='chat-save-dialog')invalidateSavePreview();return;}
  if(target.dataset.view){view=target.dataset.view;applyView();return;}
  if(target.dataset.conversation){selectConversation(target.dataset.conversation);return;}
  if(target.dataset.suggestion){$('#chat-input').value=target.dataset.suggestion;$('#chat-input').focus?.();return;}
  if(target.dataset.saveAnswer!==undefined){openChatSave(Number(target.dataset.saveAnswer),'answer');return;}
  if(target.dataset.workerStop!==undefined){Promise.resolve(controlParallelWorker(target.dataset.workerStop,'stop')).catch(error=>toast(error.message));return;}
  if(target.dataset.workerRetry!==undefined){Promise.resolve(controlParallelWorker(target.dataset.workerRetry,'retry')).catch(error=>toast(error.message));return;}
  if(target.dataset.watchRun!==undefined){Promise.resolve(runWatchItem(target.dataset.watchRun)).catch(error=>toast(error.message));return;}
  if(target.dataset.watchIgnore!==undefined){Promise.resolve(ignoreWatchItem(target.dataset.watchIgnore)).catch(error=>toast(error.message));return;}
  if(target.dataset.answerIndex!==undefined){focusAnswer(Number(target.dataset.answerIndex));return;}
  if(target.dataset.referenceId){const owner=event.target.closest?.('[data-answer-index]'),provisional=Boolean(event.target.closest?.('.pending'));openCitationReference(target.dataset.referenceId,owner?Number(owner.dataset.answerIndex):null,provisional);return;}
  if(target.dataset.source){selected=target.dataset.source;renderBoard();renderGraph();renderDetail();return;}
  if(target.dataset.selectPage){selectedPage=target.dataset.selectPage;renderGraph();renderProjectDetail();return;}
  if(target.dataset.page){selectedPage=target.dataset.page;renderKnowledgeGraph();openPage(target.dataset.page);return;}
  if(target.dataset.graph){graphMode=target.dataset.graph;$$('[data-graph]').forEach(button=>{button.classList.toggle('active',button===target);button.setAttribute('aria-pressed',String(button===target));});renderGraph();return;}
  Promise.resolve((async()=>{switch(target.dataset.action){
    case'chat-top':jumpChat('top');break; case'chat-bottom':jumpChat('bottom');break;
    case'new-chat':newConversation();break; case'clear-history':clearHistory();break; case'toggle-knowledge':toggleKnowledge();break;
    case'save-conversation':openChatSave(latestAssistantIndex(currentConversation()),'conversation');break;
    case'chat-preview-refresh':await requestChatSavePreview();break;
    case'show-watch':view='watch';applyView();$('#automation-panel').scrollIntoView?.({block:'start'});break;
    case'queue-previous':await moveWatchQueuePage(-1);break;case'queue-next':await moveWatchQueuePage(1);break;
    case'chat-stop':await stopChat();break; case'reconnect-chat':await reconnectChat();break; case'retry-chat':{const conversation=currentConversation(),last=conversation?.messages.at(-1);if(last?.role==='user')await submitChat(last.content,{reuseLast:true});break;}
    case'open-index':openPage(state.graph.nodes.find(node=>node.id==='wiki/_meta/index.md')?.id||state.graph.nodes[0]?.id);break;
    case'connect':openDialog('#connect-dialog');break;case'retrieval-status-details':renderRetrievalStatus();openDialog('#retrieval-status-dialog');break;case'refresh-retrieval-status':requestRetrievalStatus(true);break;case'choose-folder':await chooseFolder();break;case'browse-folders':openFolderBrowser();break;case'folder-browser-up':if(folderBrowserLocation?.parent)await browseFolders(folderBrowserLocation.parent);break;case'folder-browser-go':if(typeof target.dataset.path==='string')await browseFolders(target.dataset.path);break;case'folder-browser-select':selectFolderBrowser();break;case'new-task':openTask();break;case'steer':openTask('steer');break;
    case'resume-integration':await resumeParallelIntegration();toast('준비된 초안 통합을 다시 시작했습니다.');break;
    case'stop':await api('stop',{});toast('중단을 요청했습니다. 반영된 파일과 기록은 유지됩니다.');await refresh(true);break;
    case'refresh':await refresh(true);toast('현재 상태를 확인했습니다.');break;
    case'blocked':blockedOnly=!blockedOnly;target.setAttribute('aria-pressed',String(blockedOnly));renderBoard();break;
    case'zoom-in':zoom=Math.min(2,zoom+.2);renderGraph();break;case'zoom-out':zoom=Math.max(.6,zoom-.2);renderGraph();break;case'zoom-reset':zoom=1;renderGraph();break;
    case'upload':if(state?.demo)openDialog('#connect-dialog');else if(isProject())toast('프로젝트 모드에서는 자료를 추가하지 않습니다.');else $('#file-upload').click();break;
  }})()).catch(error=>toast(error.message));
}
document.addEventListener('click',handleClick);
$('#chat-messages').addEventListener('scroll',updateChatScrollControls,{passive:true});
$('#chat-messages').addEventListener('toggle',updateChatScrollControls,true);
document.addEventListener('keydown',event=>{
  if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();view='chat';applyView();$('#chat-input').focus();}
  if(['Enter',' '].includes(event.key)&&event.target.matches?.('.graph-node,.knowledge-node')){event.preventDefault();openPage(event.target.dataset.page);}
});
document.addEventListener('input',event=>{if(event.target.closest?.('#watch-config-form'))captureWatchDraft(event.target.closest('#watch-config-form'));});
document.addEventListener('change',event=>{if(event.target.closest?.('#watch-config-form'))captureWatchDraft(event.target.closest('#watch-config-form'));});
document.addEventListener('submit',event=>{if(event.target.id==='watch-config-form'){event.preventDefault();Promise.resolve(applyWatchConfig()).catch(error=>toast(error.message));}});
$('#chat-form').addEventListener('submit',event=>{event.preventDefault();const input=$('#chat-input'),message=input.value;input.value='';submitChat(message);});
$('#chat-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('#chat-form').requestSubmit?.();}});
$('#search').addEventListener('input',event=>{query=event.target.value;renderBoard();renderGraph();renderLibrary();});
$('#connect-dialog').addEventListener('close',()=>{invalidateFolderPicker();invalidateFolderBrowser({close:true});});
$('#folder-browser-dialog').addEventListener('close',()=>{invalidateFolderBrowser();if($('#connect-dialog').open)$('#connect-root').focus?.();});
$('#connect-root').addEventListener('input',()=>{if(folderPickerPending)invalidateFolderPicker();if($('#folder-browser-dialog').open)invalidateFolderBrowser({close:true});});
$('#connect-form').addEventListener('submit',async event=>{event.preventDefault();if(folderPickerPending){$('.form-error',event.target).textContent='폴더 선택이 끝난 뒤 연결해 주세요.';return;}const button=$('[type=submit]',event.target);button.disabled=true;try{await api('connect',{root:new FormData(event.target).get('root')});selected=null;lastRender='';$('#connect-dialog').close();await refresh(true);toast('내 위키를 연결했습니다.');}catch(error){$('.form-error',event.target).textContent=error.message;}finally{button.disabled=false;}});
$('#task-form').addEventListener('submit',async event=>{event.preventDefault();const button=$('[type=submit]',event.target);button.disabled=true;const form=new FormData(event.target);try{const sources=form.getAll('source');await api(taskMode,{message:form.get('message'),sources,model:form.get('model'),...(parallelPreparationAvailable()&&sources.length>1?{parallelism:Number(form.get('parallelism'))||3}:{})});$('#task-dialog').close();await refresh(true);toast(taskMode==='steer'?'추가 지시를 전달했습니다.':'Pi에 작업을 맡겼습니다.');}catch(error){$('.form-error',event.target).textContent=error.message;}finally{button.disabled=false;}});
$('#chat-save-form').addEventListener('input',event=>{if(event.target.matches?.('[name="title"]'))markSavePreviewStale();});
$('#chat-save-form').addEventListener('change',event=>{if(event.target.matches?.('[name="scope"]'))markSavePreviewStale();});
$('#chat-save-form').addEventListener('submit',async event=>{event.preventDefault();const button=$('#chat-save-submit');if(button.disabled)return;button.disabled=true;$('.form-error',event.target).textContent='';try{await commitChatSave();await refresh(true);}catch(error){handleChatSaveError(error,event.target);} });
$('#file-upload').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>2_000_000)throw new Error('2MB 이하의 Markdown 파일을 선택하세요.');await api('upload',{name:file.name,content:await file.text()});await refresh(true);toast('자료를 추가했습니다.');}catch(error){toast(error.message);}finally{event.target.value='';}});

async function start(){try{token=(await api('session')).token;}catch(error){toast(error.message);}await refresh(true);setInterval(()=>{if(!document.hidden)refresh();},2500);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh(true);});}
globalThis.WikiStudioApp = globalThis.WikiStudioApp || {};
globalThis.WikiStudioApp.start = start;
