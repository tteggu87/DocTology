'use strict';

(function(namespace) {
  namespace.createRetrievalUsage = function createRetrievalUsage({escapeHTML}) {
    const lanes = Object.freeze(['grep', 'fts', 'wikilinks', 'vector']);
    const isFiniteNonnegativeInteger = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;

    function normalize(value) {
      if (!value || typeof value !== 'object' || Array.isArray(value) || value.version !== 1 || value.basis !== 'successful_discovery_calls') return null;
      const exactLaneCounts = candidate => candidate && typeof candidate === 'object' && !Array.isArray(candidate) && Object.keys(candidate).length === lanes.length && lanes.every(key => Object.hasOwn(candidate, key) && isFiniteNonnegativeInteger(candidate[key]));
      if (!exactLaneCounts(value.counts) || !Number.isSafeInteger(lanes.reduce((sum, key) => sum + value.counts[key], 0)) || !isFiniteNonnegativeInteger(value.listCalls) || !isFiniteNonnegativeInteger(value.readCalls) || !Array.isArray(value.unsupported)) return null;
      const unsupported = [];
      for (const lane of value.unsupported) {
        if (typeof lane !== 'string' || !lanes.includes(lane) || unsupported.includes(lane) || value.counts[lane] !== 0) return null;
        unsupported.push(lane);
      }
      if (value.results != null && !exactLaneCounts(value.results)) return null;
      return {version:1, basis:'successful_discovery_calls', counts:Object.fromEntries(lanes.map(key => [key, value.counts[key]])), ...(value.results != null ? {results:Object.fromEntries(lanes.map(key => [key, value.results[key]]))} : {}), listCalls:value.listCalls, readCalls:value.readCalls, unsupported};
    }

    function retrievalUsageShares(counts) {
      const total = lanes.reduce((sum, key) => sum + counts[key], 0);
      if (!total) return null;
      const rows = lanes.map((key, index) => ({key, index, raw:counts[key] * 100 / total, share:Math.floor(counts[key] * 100 / total)}));
      const remaining = 100 - rows.reduce((sum, row) => sum + row.share, 0);
      rows.sort((a, b) => (b.raw - b.share) - (a.raw - a.share) || a.index - b.index).slice(0, remaining).forEach(row => { row.share += 1; });
      return Object.fromEntries(rows.map(row => [row.key, row.share]));
    }

    function render(usage) {
      if (!usage) return '<section class="search-usage" aria-label="검색 호출 구성"><div class="search-usage-heading"><strong>검색 호출 구성</strong></div><p class="search-usage-empty">검색 사용량 기록 없음</p></section>';
      const labels = {grep:'grep 방식', fts:'FTS', wikilinks:'위키링크', vector:'벡터'};
      const percentages = retrievalUsageShares(usage.counts);
      const total = lanes.reduce((sum, key) => sum + usage.counts[key], 0);
      const rows = lanes.map(key => {
        const unsupported = usage.unsupported.includes(key), count = usage.counts[key], share = percentages?.[key];
        return `<li class="search-usage-lane${unsupported?' unsupported':''}" data-search-lane="${key}"><span>${labels[key]}</span><strong>${unsupported?'채팅 미연결 · 관측 호출 0회':`${count}회`}</strong>${percentages?`<small>비율 ${share}%</small><i aria-hidden="true"><b style="width:${share}%"></b></i>`:'<small>비율 없음</small>'}</li>`;
      }).join('');
      const results = usage.results ? `<details class="search-usage-results"><summary>검색 결과 수 · 인용 또는 고유 문서 수가 아님</summary><ul>${lanes.map(key => `<li>${labels[key]} ${usage.results[key]}건</li>`).join('')}</ul></details>` : '';
      return `<section class="search-usage" aria-label="검색 호출 구성"><div class="search-usage-heading"><strong>검색 호출 구성</strong><span>성공한 검색·링크 호출 ${total}회</span></div><ul class="search-usage-lanes">${rows}</ul><p class="search-usage-meta">목록 호출 ${usage.listCalls}회 · 본문 읽기 ${usage.readCalls}회</p><p class="search-usage-note">목록·본문 읽기·실패 제외; 답변 기여도/정확도가 아님</p>${results}</section>`;
    }

    function renderCandidates(candidates, exploration = null) {
      if (!candidates?.length) return '';
      const readDocuments = Boolean(exploration);
      const label = readDocuments ? '읽은 문서' : '검색 후보';
      const note = readDocuments ? 'wiki_read로 실제 읽은 문서이며, 답변의 인용과는 다릅니다' : '답변의 인용과 다릅니다';
      return `<details class="candidate-box"><summary>${label} ${candidates.length}개 <span>${note}</span></summary><div>${candidates.map(candidate => `<span class="candidate-chip">${escapeHTML(candidate.title)}</span>`).join('')}</div></details>`;
    }

    function explorationEventLabel(event) {
      const fields = [];
      if (event.path) fields.push(`경로: ${event.path}`);
      if (event.query) fields.push(`검색: ${event.query}`);
      if (event.count != null) fields.push(`${event.count}${event.tool === 'wiki_read' ? '자' : '개'}`);
      if (event.status) fields.push(event.status);
      return fields.join(' · ');
    }

    function renderExploration(exploration) {
      if (!exploration) return '';
      const eventRows = exploration.events.map(event => `<li><code>${escapeHTML(event.tool)}</code>${explorationEventLabel(event) ? `<span>${escapeHTML(explorationEventLabel(event))}</span>` : ''}</li>`).join('');
      const limit = exploration.limits ? ` / 한도 호출 ${exploration.limits.calls}, 읽기 ${exploration.limits.reads}` : '';
      const traceScope = exploration.calls > exploration.events.length ? ' · 최근 24개 도구 호출' : ' · 전체 도구 호출 표시';
      return `<section class="exploration-activity" aria-label="실제 위키 도구 활동"><details><summary>도구 활동 · 호출 ${exploration.calls}회 · 문서 읽기 ${exploration.readCount}개${escapeHTML(limit)}</summary>${eventRows ? `<p class="tool-trace-scope">${traceScope}</p><ol class="tool-trace">${eventRows}</ol>` : '<p>아직 표시할 도구 호출이 없습니다.</p>'}</details>${exploration.invalidatedReadCount ? `<p class="exploration-warning" role="status">문서 변경으로 읽은 근거 ${exploration.invalidatedReadCount}개가 무효화되었습니다. 현재 읽기 수 ${exploration.readCount}개는 유지됩니다.</p>` : ''}${exploration.exhausted ? '<p class="exploration-warning" role="status">탐색 한도에 도달했습니다. 완료를 뜻하지 않으며, 읽은 근거만으로 답변을 마무리합니다.</p>' : ''}</section>`;
    }

    return {lanes, normalize, retrievalUsageShares, render, renderCandidates, explorationEventLabel, renderExploration};
  };
})(globalThis.WikiStudioModules = globalThis.WikiStudioModules || {});
