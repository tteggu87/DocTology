'use strict';

(function(namespace) {
  namespace.createRetrievalStatusTools = function createRetrievalStatusTools({escapeHTML}) {
    const retrievalStateLabels = {off:'꺼짐', missing:'인덱스 없음', current:'최신(stat)', stale:'인덱스 오래됨', unknown:'확인 불가', error:'오류', not_applicable:'해당 없음'};
    const onnxStateLabels = {runtime_missing:'런타임 없음', not_configured:'설정 안 됨', artifacts_missing:'파일 없음', configured:'설정됨 · 추론 미검증', unknown:'확인 불가', not_applicable:'해당 없음'};
    const isFiniteNonnegativeInteger = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
    const nullableBoolean = value => typeof value === 'boolean' ? value : null;
    const nullableCount = value => isFiniteNonnegativeInteger(value) ? value : null;

    function normalizeRetrievalStatus(value, expectedRoot) {
      const sqliteStates = new Set(Object.keys(retrievalStateLabels));
      const onnxStates = new Set(Object.keys(onnxStateLabels));
      const vectorStates = new Set(['none', 'stored', 'unknown', 'not_applicable']);
      if (!value || typeof value !== 'object' || Array.isArray(value) || value.version !== 1 || typeof value.root !== 'string' || value.root !== expectedRoot || !value.sqlite || !value.onnx || !value.vectors || !value.chatMethods) return null;
      const sqlite = value.sqlite, onnx = value.onnx, vectors = value.vectors, methods = value.chatMethods;
      if (!sqliteStates.has(sqlite.state) || !['stat', 'unknown'].includes(sqlite.freshness) || !onnxStates.has(onnx.state) || !vectorStates.has(vectors.state) || typeof methods.grep !== 'boolean' || typeof methods.fts !== 'boolean' || typeof methods.wikilinks !== 'boolean' || typeof methods.vector !== 'boolean') return null;
      const packages = onnx.packages && typeof onnx.packages === 'object' && !Array.isArray(onnx.packages)
        ? {onnxruntime:nullableBoolean(onnx.packages.onnxruntime), tokenizers:nullableBoolean(onnx.packages.tokenizers), numpy:nullableBoolean(onnx.packages.numpy)}
        : {onnxruntime:null, tokenizers:null, numpy:null};
      return {version:1, root:value.root, checkedAt:typeof value.checkedAt === 'number' && Number.isFinite(value.checkedAt) ? value.checkedAt : null, sqlite:{configured:nullableBoolean(sqlite.configured), state:sqlite.state, freshness:sqlite.freshness, pages:nullableCount(sqlite.pages), chunks:nullableCount(sqlite.chunks), fts:nullableBoolean(sqlite.fts), reasons:Array.isArray(sqlite.reasons) ? sqlite.reasons.filter(code => typeof code === 'string').slice(0, 12) : []}, onnx:{state:onnx.state, packages, modelConfigured:nullableBoolean(onnx.modelConfigured), modelPresent:nullableBoolean(onnx.modelPresent), tokenizerConfigured:nullableBoolean(onnx.tokenizerConfigured), tokenizerPresent:nullableBoolean(onnx.tokenizerPresent), inferenceVerified:false}, vectors:{state:vectors.state, rows:nullableCount(vectors.rows)}, chatMethods:{grep:methods.grep, fts:methods.fts, wikilinks:methods.wikilinks, vector:methods.vector}};
    }

    function retrievalStatusMode(state, retrievalStatus, retrievalStatusRoot) {
      if (state?.demo) return 'demo';
      if (!state?.root) return 'none';
      if (retrievalStatusRoot !== String(state.root)) return 'unknown';
      return retrievalStatus?.kind || (retrievalStatus ? 'current' : 'unknown');
    }

    function renderRetrievalStatus({state, retrievalStatus, retrievalStatusRoot, $}) {
      const mode = retrievalStatusMode(state, retrievalStatus, retrievalStatusRoot);
      const status = mode === 'current' ? retrievalStatus : null;
      let sqliteDetail = '확인 불가', onnxDetail = '확인 불가', sqliteTone = 'unknown', onnxTone = 'unknown';
      if (mode === 'demo' || mode === 'unsupported') { sqliteDetail = '지원 안함'; onnxDetail = '지원 안함'; }
      else if (status) { sqliteDetail = retrievalStateLabels[status.sqlite.state]; onnxDetail = onnxStateLabels[status.onnx.state]; sqliteTone = status.sqlite.state === 'current' ? 'neutral' : status.sqlite.state; onnxTone = status.onnx.state === 'configured' ? 'neutral' : status.onnx.state; }
      const badge = (label, detail, tone) => `<button type="button" class="readiness-badge ${tone}" data-action="retrieval-status-details" aria-label="${escapeHTML(label)} ${escapeHTML(detail)} · 검색 준비 상태 상세 보기"><strong>${escapeHTML(label)}</strong><span>${escapeHTML(detail)}</span></button>`;
      $('#retrieval-readiness').innerHTML = badge('SQLite', sqliteDetail, sqliteTone) + badge('ONNX', onnxDetail, onnxTone);
      const body = $('#retrieval-status-body'), updated = $('#retrieval-status-updated');
      if (!status) { updated.textContent = mode === 'demo' ? '예시 작업실에서는 확인하지 않습니다.' : mode === 'unsupported' ? '이 서버는 검색 준비 상태 API를 제공하지 않습니다.' : mode === 'error' ? '상태를 확인하지 못했습니다. 다시 확인해도 설정을 변경하지 않습니다.' : '연결된 실제 위키의 상태를 기다리고 있습니다.'; body.innerHTML = ''; return; }
      updated.textContent = status.checkedAt ? `${new Date(status.checkedAt * 1000).toLocaleString('ko-KR')} 기준` : '확인 시각 없음';
      const yesNo = value => value === true ? '있음' : value === false ? '없음' : '확인 불가';
      const fts = status.sqlite.fts === true ? '사용 가능' : status.sqlite.fts === false ? '사용 불가' : '확인 불가';
      const chat = value => value ? '연결됨' : '미연결';
      body.innerHTML = `<section><h3>SQLite</h3><p>설정 ${yesNo(status.sqlite.configured)} · ${escapeHTML(retrievalStateLabels[status.sqlite.state])}</p><p>인덱스 신선도: ${status.sqlite.freshness === 'stat' && ['current','stale'].includes(status.sqlite.state) ? '파일 상태(stat) 기준, 내용 일치의 정확한 증명은 아님' : '확인 불가'}</p><p>페이지 ${status.sqlite.pages == null ? '확인 불가' : status.sqlite.pages+'개'} · 청크 ${status.sqlite.chunks == null ? '확인 불가' : status.sqlite.chunks+'개'} · FTS ${fts} · 채팅 ${chat(status.chatMethods.fts)}</p>${status.sqlite.reasons.length ? `<p class="retrieval-reasons">사유: ${escapeHTML(status.sqlite.reasons.join(', '))}</p>` : ''}</section><section><h3>ONNX</h3><p>${escapeHTML(onnxStateLabels[status.onnx.state])}</p><p>패키지: onnxruntime ${yesNo(status.onnx.packages.onnxruntime)} · tokenizers ${yesNo(status.onnx.packages.tokenizers)} · numpy ${yesNo(status.onnx.packages.numpy)}</p><p>모델 설정 ${yesNo(status.onnx.modelConfigured)} · 모델 파일 ${yesNo(status.onnx.modelPresent)} · 토크나이저 설정 ${yesNo(status.onnx.tokenizerConfigured)} · 토크나이저 파일 ${yesNo(status.onnx.tokenizerPresent)}</p><p>설정됨은 추론 실행이나 준비 완료를 뜻하지 않습니다. 추론 미검증</p></section><section><h3>벡터</h3><p>${({stored:'저장된 벡터',none:'저장된 벡터 없음',unknown:'확인 불가',not_applicable:'해당 없음'})[status.vectors.state]}${status.vectors.rows != null ? ' · '+status.vectors.rows+'행' : ''}</p><p>저장 행 수는 품질 또는 준비 완료를 뜻하지 않습니다. 채팅 ${chat(status.chatMethods.vector)}</p></section>`;
    }

    return {normalizeRetrievalStatus, renderRetrievalStatus};
  };
})(globalThis.WikiStudioModules = globalThis.WikiStudioModules || {});
