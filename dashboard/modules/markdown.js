'use strict';

(function(namespace) {
  namespace.createMarkdownRenderer = function createMarkdownRenderer({escapeHTML, knownDocumentIds}) {
    function resolveInternalLink(href, documentPath = '', references = []) {
      try {
        const url = new URL(String(href).replace(/&amp;/g, '&'), 'http://wiki.local/' + documentPath);
        if (url.origin !== 'http://wiki.local') return null;
        const id = decodeURIComponent(url.pathname.slice(1));
        return knownDocumentIds(references).has(id) ? id : null;
      } catch {
        return null;
      }
    }

    function renderInline(text, documentPath = '', references = [], includeCitations = false) {
      const tokens = [];
      let safe = escapeHTML(text);
      safe = safe.replace(/(?<!!)\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, href) => {
        const id = resolveInternalLink(href, documentPath, references);
        if (!id) return label;
        const token = `@@DT${tokens.length}@@`;
        tokens.push(`<button class="wiki-inline-link" data-page="${escapeHTML(id)}">${label}</button>`);
        return token;
      });
      if (includeCitations) {
        safe = safe.replace(/\[(\d+)\]/g, (match, numberText) => {
          const number = Number(numberText);
          const reference = references.find(item => item.number === number);
          if (!reference) return match;
          const token = `@@DT${tokens.length}@@`;
          tokens.push(`<button class="citation-link" data-citation-number="${number}" data-reference-id="${escapeHTML(reference.id)}" aria-label="참고문헌 ${number} 열기">[${number}]</button>`);
          return token;
        });
      }
      safe = safe.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      safe = safe.replace(/\[\[([^\]]+)\]\]/g, (_match, value) => {
        const [target, label] = value.split('|');
        const key = target.split('#')[0];
        const matches = [...knownDocumentIds(references)].filter(id => [
          id,
          id.replace(/\.md$/, ''),
          id.split('/').at(-1).replace(/\.md$/, '')
        ].includes(key));
        return matches.length === 1
          ? `<button class="wiki-inline-link" data-page="${escapeHTML(matches[0])}">${escapeHTML(label || target)}</button>`
          : escapeHTML(value);
      });
      tokens.forEach((html, index) => { safe = safe.replace(`@@DT${index}@@`, html); });
      return safe;
    }

    function renderMarkdown(text, documentPath = '', references = [], includeCitations = false) {
      const clean = String(text || '').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
      let inCode = false;
      let code = [];
      let list = [];
      const result = [];
      const flushList = () => {
        if (!list.length) return;
        result.push(`<ul>${list.join('')}</ul>`);
        list = [];
      };
      for (const line of clean.split('\n')) {
        if (line.startsWith('```')) {
          flushList();
          if (inCode) {
            result.push(`<pre><code>${escapeHTML(code.join('\n'))}</code></pre>`);
            code = [];
          }
          inCode = !inCode;
          continue;
        }
        if (inCode) { code.push(line); continue; }
        const heading = line.match(/^(#{1,3})\s+(.+)/);
        if (heading) {
          flushList();
          result.push(`<h${heading[1].length}>${renderInline(heading[2], documentPath, references, includeCitations)}</h${heading[1].length}>`);
          continue;
        }
        const bullet = line.match(/^[-*]\s+(.+)/);
        if (bullet) { list.push(`<li>${renderInline(bullet[1], documentPath, references, includeCitations)}</li>`); continue; }
        flushList();
        if (line.trim()) result.push(`<p>${renderInline(line, documentPath, references, includeCitations)}</p>`);
      }
      flushList();
      if (code.length) result.push(`<pre><code>${escapeHTML(code.join('\n'))}</code></pre>`);
      return result.join('');
    }

    function suggestedPrompts(nodes) {
      const frames = [
        title => `“${title}”의 핵심을 근거와 함께 설명해줘`,
        title => `“${title}”와 연결된 문서를 비교해줘`,
        title => `“${title}”에서 아직 불확실한 점을 찾아줘`,
        title => `“${title}”를 처음 읽는 사람에게 안내해줘`
      ];
      return (nodes || []).filter(node => node?.title).slice(0, 4).map((node, index) => ({
        id:node.id,
        text:frames[index % frames.length](node.title)
      }));
    }

    function renderEmptyChat(state, icon) {
      const prompts = suggestedPrompts(state?.graph?.nodes);
      return `<div class="chat-empty"><div class="empty-mark">D</div><span class="eyebrow">ASK YOUR WIKI</span><h1>지식의 연결을 따라<br>대화를 시작하세요.</h1><p>${state?.graph?.nodes?.length ? `${escapeHTML(state.name)}의 ${state.graph.nodes.length}개 문서를 읽을 준비가 됐습니다.` : '위키를 연결하면 문서와 원문을 근거로 답합니다.'}</p><div id="suggested-prompts" class="suggested-prompts">${prompts.map(prompt => `<button type="button" data-suggestion="${escapeHTML(prompt.text)}"><span>${escapeHTML(prompt.text)}</span>${icon('arrow')}</button>`).join('')}</div></div>`;
    }

    return {
      resolveInternalLink,
      renderInline,
      renderMarkdown,
      renderAnswerMarkdown:(text, references = []) => renderMarkdown(text, '', references, true),
      suggestedPrompts,
      renderEmptyChat
    };
  };
})(globalThis.WikiStudioModules = globalThis.WikiStudioModules || {});
