'use strict';

(function(namespace) {
  namespace.createHistoryCodec = function createHistoryCodec(dependencies) {
    const {limits, now = () => Date.now(), byteSize, normalizeRetrievalUsage} = dependencies;
    const boundedText = (value, limit) => String(value ?? '').slice(0, limit);
    const boundedCount = value => Math.max(0, Math.min(1000000, Math.floor(Number(value) || 0)));
    const normalizeContentHash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) ? value : '';

    function normalizeReadRanges(value) {
      return Array.isArray(value) ? value.slice(0, 64).flatMap(range => {
        const offset = Number(range?.offset), end = Number(range?.end);
        return Number.isSafeInteger(offset) && Number.isSafeInteger(end) && offset >= 0 && end >= offset && end <= 1000000000 ? [{offset, end}] : [];
      }) : [];
    }

    function normalizeReference(reference, index) {
      const rawSources = Array.isArray(reference?.rawSources)
        ? reference.rawSources.filter(item => item && item.id).slice(0, limits.evidence).map(item => ({id:boundedText(item.id, 1000), title:boundedText(item.title || item.id, 500)}))
        : [];
      const contentHash = normalizeContentHash(reference?.contentHash);
      const readRanges = normalizeReadRanges(reference?.readRanges);
      return {id:boundedText(reference?.id, 1000), title:boundedText(reference?.title || reference?.id || `참고문헌 ${index + 1}`, 500), number:Number(reference?.number) || index + 1, excerpt:boundedText(reference?.excerpt, limits.excerpt), rawSources, ...(contentHash ? {contentHash} : {}), ...(readRanges.length ? {readRanges} : {})};
    }

    const normalizeReferences = items => Array.isArray(items) ? items.slice(0, limits.evidence).map(normalizeReference) : [];

    function normalizeSaved(value) {
      if (!value || typeof value !== 'object' || !value.itemId || !value.sourcePath) return null;
      return {itemId:boundedText(value.itemId, 300), sourcePath:boundedText(value.sourcePath, 1200), root:boundedText(value.root, 1200), savedAt:Number(value.savedAt) || now(), scope:value.scope === 'conversation' ? 'conversation' : 'answer'};
    }

    function normalizeExploration(value) {
      if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
      const toolNames = new Set(['wiki_list', 'wiki_search', 'wiki_read', 'wiki_links']);
      const events = Array.isArray(value.events) ? value.events.slice(-limits.explorationEvents).flatMap(event => {
        if (!event || typeof event !== 'object' || !toolNames.has(event.tool)) return [];
        const normalized = {tool:event.tool};
        if (event.path != null) normalized.path = boundedText(event.path, limits.explorationText);
        if (event.query != null) normalized.query = boundedText(event.query, limits.explorationText);
        if (event.status != null) normalized.status = boundedText(event.status, 120);
        if (event.count != null) normalized.count = boundedCount(event.count);
        return [normalized];
      }) : [];
      const detail = value.limits && typeof value.limits === 'object' && !Array.isArray(value.limits)
        ? {calls:boundedCount(value.limits.calls), reads:boundedCount(value.limits.reads)}
        : null;
      return {calls:boundedCount(value.calls), readCount:boundedCount(value.readCount), invalidatedReadCount:boundedCount(value.invalidatedReadCount), events, limits:detail, exhausted:value.exhausted === true, retrievalUsage:normalizeRetrievalUsage(value.retrievalUsage)};
    }

    function normalizeConversation(value) {
      const conversation = value && typeof value === 'object' ? value : {};
      const messages = Array.isArray(conversation.messages)
        ? conversation.messages.filter(message => ['user','assistant'].includes(message?.role)).slice(-limits.messages).map(message => ({role:message.role, content:boundedText(message.content, limits.messageText), truncated:Boolean(message.truncated) || String(message.content || '').length > limits.messageText, partial:Boolean(message.partial), references:normalizeReferences(message.references), candidates:normalizeReferences(message.candidates), exploration:normalizeExploration(message.exploration), createdAt:Number(message.createdAt) || now(), save:normalizeSaved(message.save)}))
        : [];
      return {id:boundedText(conversation.id || `local-${now()}`, 200), title:boundedText(conversation.title || '새 대화', 200), createdAt:Number(conversation.createdAt) || now(), updatedAt:Number(conversation.updatedAt) || now(), messages, historyTruncated:Boolean(conversation.historyTruncated) || (Array.isArray(conversation.messages) && conversation.messages.length > limits.messages), saves:Array.isArray(conversation.saves) ? conversation.saves.map(normalizeSaved).filter(Boolean).slice(-12) : [], job:conversation.job && conversation.job.id ? {id:boundedText(conversation.job.id, 200), status:boundedText(conversation.job.status || 'running', 30), startedAt:Number(conversation.job.startedAt) || 0} : null, error:boundedText(conversation.error, 2000)};
    }

    function buildHistoryPayload(conversations, activeConversationId) {
      const ordered = [...conversations].sort((a, b) => Number(b.id === activeConversationId) - Number(a.id === activeConversationId) || b.updatedAt - a.updatedAt).slice(0, limits.conversations);
      const payload = {activeConversationId, conversations:[], truncated:conversations.length > limits.conversations};
      let estimated = byteSize(JSON.stringify(payload));
      for (const conversation of ordered) {
        const stored = normalizeConversation(conversation);
        const messages = stored.messages;
        stored.messages = [];
        const shellBytes = byteSize(JSON.stringify(stored)) + 1;
        if (estimated + shellBytes > limits.storageBytes - 512) { payload.truncated = true; continue; }
        payload.conversations.push(stored);
        estimated += shellBytes;
        for (const message of messages.slice().reverse()) {
          const messageBytes = byteSize(JSON.stringify(message)) + 1;
          if (estimated + messageBytes <= limits.storageBytes - 512) { stored.messages.unshift(message); estimated += messageBytes; }
          else { stored.historyTruncated = true; payload.truncated = true; }
        }
      }
      let json = JSON.stringify(payload);
      while (byteSize(json) > limits.storageBytes && payload.conversations.length) {
        const oldest = payload.conversations.at(-1);
        if (oldest.messages.length) { oldest.messages.shift(); oldest.historyTruncated = true; }
        else payload.conversations.pop();
        payload.truncated = true;
        json = JSON.stringify(payload);
      }
      return {json, bytes:byteSize(json), truncated:payload.truncated || payload.conversations.some(conversation => conversation.historyTruncated || conversation.messages.some(message => message.truncated))};
    }

    function chatHistoryPayload(messages) {
      let remaining = 24000;
      const result = [];
      for (const message of messages.slice(-12).reverse()) {
        if (remaining <= 0) break;
        const content = String(message.content || '').slice(-Math.min(6000, remaining));
        remaining -= content.length;
        result.unshift({role:message.role, content});
      }
      return result;
    }

    return {boundedText, boundedCount, normalizeContentHash, normalizeReadRanges, normalizeReference, normalizeReferences, normalizeSaved, normalizeExploration, normalizeConversation, buildHistoryPayload, chatHistoryPayload};
  };
})(globalThis.WikiStudioModules = globalThis.WikiStudioModules || {});
