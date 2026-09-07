'use strict';
(function(namespace){
  namespace.createNativePiTools=function({escapeHTML}){
    const text=(value,limit=1000)=>typeof value==='string'?value.slice(0,limit):'';
    const number=value=>Number.isSafeInteger(value)&&value>=0?value:null;
    function normalize(value){
      if(!value||typeof value!=='object'||Array.isArray(value))return null;
      const tokens=value.stats?.tokens;
      const stats=tokens&&typeof tokens==='object'?{tokens:Object.fromEntries(['input','output','cacheRead','cacheWrite','total'].map(key=>[key,number(tokens[key])])),contextUsage:value.stats?.contextUsage&&typeof value.stats.contextUsage==='object'?{tokens:number(value.stats.contextUsage.tokens),contextWindow:number(value.stats.contextUsage.contextWindow)}:null}:null;
      const tools=Array.isArray(value.tools)?value.tools.slice(-32).filter(row=>row&&typeof row==='object').map(row=>({id:text(row.id,200),tool:text(row.tool,100),status:['running','ok','error'].includes(row.status)?row.status:'running',args:text(row.args,1000),output:text(row.output,3000)})):[];
      const request=value.interaction;
      const interaction=request&&['confirm','select','input','editor'].includes(request.method)?{id:text(request.id,200),method:request.method,title:text(request.title),message:text(request.message,2000),options:Array.isArray(request.options)?request.options.slice(0,40).map(option=>text(option,500)):[],initialValue:text(request.initialValue,8000)}:null;
      return {readDocuments:Array.isArray(value.readDocuments)?value.readDocuments.slice(-64).filter(row=>row&&typeof row.id==='string').map(row=>({id:text(row.id,1000),title:text(row.title,500)})):[],citationNotice:text(value.citationNotice),sessionId:text(value.sessionId,200),model:text(value.model,200),thinkingLevel:text(value.thinkingLevel,80),notice:text(value.notice),tools,toolCalls:number(value.toolCalls),stats,interaction,truncated:value.truncated===true,commandOnly:value.commandOnly===true};
    }
    function render(value,{progress=null,processRunning=false}={}){
      const native=normalize(value);if(!native)return '';
      const tokens=native.stats?.tokens;
      const context=native.stats?.contextUsage;
      const counts=tokens?`세션 누적 · 입력 ${tokens.input??'미측정'} · 출력 ${tokens.output??'미측정'} · 캐시 읽기 ${tokens.cacheRead??'미측정'} · 캐시 쓰기 ${tokens.cacheWrite??'미측정'} 토큰`:'토큰·캐시 사용량은 Pi 응답 후 확인합니다.';
      const phases={starting:'Pi 세션 준비',waiting:'모델 응답 대기',model:'모델 처리 신호 수신',tool:'도구 실행',answer:'답변 작성',finished:'응답 완료',stopped:'응답 중단',failed:'응답 확인 실패'};
      const age=Number.isFinite(progress?.lastSignalAt)?Math.max(0,Math.floor(Date.now()/1000-progress.lastSignalAt)):null;
      const activity=progress?`<p>${escapeHTML(native.interaction?'사용자 입력 대기':phases[progress.phase]||'Pi 상태 확인')} · ${processRunning?'Pi 실행 중':'프로세스 상태 확인'}${age===null?'':` · 마지막 활동 ${age}초 전`}</p>`:'';
      return `<section class="native-pi-observation" aria-label="Pi 기본 세션 활동"><strong>Pi 기본 세션 · 실험</strong>${activity}<p>${escapeHTML(native.model||'Pi 기본 모델')}${native.thinkingLevel?' · '+escapeHTML(native.thinkingLevel):''}</p><p>${escapeHTML(counts)}</p>${context?`<p>현재 문맥 ${context.tokens??'미측정'} / ${context.contextWindow??'미측정'} 토큰</p>`:''}<p class="field-note">FTS·벡터·링크 방식은 미측정입니다. 아래 항목은 실제 도구 호출이며 검증된 인용을 뜻하지 않습니다.</p>${native.notice?`<p>${escapeHTML(native.notice)}</p>`:''}${native.citationNotice?`<p>${escapeHTML(native.citationNotice)}</p>`:''}${native.truncated?'<p>화면 표시 한도를 넘었습니다. 전체 답변은 Pi 세션에서 확인하세요.</p>':''}<details class="native-tool-box"><summary>도구 활동 ${native.toolCalls??native.tools.length}회 · 최근 ${native.tools.length}개</summary><ol>${native.tools.map(row=>`<li><strong>${escapeHTML(row.tool)} · ${row.status==='ok'?'완료':row.status==='error'?'오류':'실행 중'}</strong>${row.args?`<pre>${escapeHTML(row.args)}</pre>`:''}${row.output?`<pre>${escapeHTML(row.output)}</pre>`:''}</li>`).join('')}</ol></details></section>`;
    }
    return {normalize,render};
  };
})(globalThis.WikiStudioModules=globalThis.WikiStudioModules||{});
