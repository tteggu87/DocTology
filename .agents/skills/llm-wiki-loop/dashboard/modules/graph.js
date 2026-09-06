'use strict';

(function(namespace) {
  namespace.createGraphTools = function createGraphTools({escapeHTML}) {
    function edgeKey(source, target) {
      return [source, target].sort().join('\u0000');
    }

    function citationFocus({nodes = [], edges = [], references = []}) {
      const nodeIds = new Set(nodes.map(node => node.id));
      const cited = new Set(references.map(reference => reference.id).filter(id => nodeIds.has(id)));
      const adjacency = new Map(nodes.map(node => [node.id, []]));

      for (const edge of edges) {
        if (!adjacency.has(edge.source) || !adjacency.has(edge.target)) continue;
        adjacency.get(edge.source).push(edge.target);
        adjacency.get(edge.target).push(edge.source);
      }

      const pathNodes = new Set(cited);
      const pathEdges = new Set();
      const citedIds = [...cited];
      if (citedIds.length === 1) {
        for (const neighbor of adjacency.get(citedIds[0]) || []) {
          pathNodes.add(neighbor);
          pathEdges.add(edgeKey(citedIds[0], neighbor));
        }
      }

      for (let first = 0; first < citedIds.length; first += 1) {
        for (let second = first + 1; second < citedIds.length; second += 1) {
          const start = citedIds[first];
          const goal = citedIds[second];
          const queue = [start];
          const previous = new Map([[start, null]]);

          while (queue.length && !previous.has(goal)) {
            const current = queue.shift();
            for (const neighbor of adjacency.get(current) || []) {
              if (previous.has(neighbor)) continue;
              previous.set(neighbor, current);
              queue.push(neighbor);
            }
          }
          if (!previous.has(goal)) continue;

          let current = goal;
          while (previous.get(current) !== null) {
            const parent = previous.get(current);
            pathNodes.add(current);
            pathNodes.add(parent);
            pathEdges.add(edgeKey(current, parent));
            current = parent;
          }
        }
      }
      return {cited, pathNodes, pathEdges};
    }

    function positions(nodes, edges, width = 680, height = 290) {
      const centerX = width / 2;
      const centerY = height / 2;
      const points = new Map(nodes.map((node, index) => [node.id, {
        x:centerX + Math.cos(index * 2.399) * Math.sqrt(index + 1) * 28,
        y:centerY + Math.sin(index * 2.399) * Math.sqrt(index + 1) * 24
      }]));

      for (let step = 0; step < 85; step += 1) {
        const forces = new Map(nodes.map(node => [node.id, {x:0, y:0}]));
        for (let first = 0; first < nodes.length; first += 1) {
          for (let second = first + 1; second < nodes.length; second += 1) {
            const a = points.get(nodes[first].id), b = points.get(nodes[second].id);
            const dx = a.x - b.x, dy = a.y - b.y;
            const distance = Math.max(12, Math.hypot(dx, dy));
            const force = 720 / (distance * distance);
            forces.get(nodes[first].id).x += dx / distance * force;
            forces.get(nodes[first].id).y += dy / distance * force;
            forces.get(nodes[second].id).x -= dx / distance * force;
            forces.get(nodes[second].id).y -= dy / distance * force;
          }
        }
        for (const edge of edges) {
          const a = points.get(edge.source), b = points.get(edge.target);
          if (!a || !b) continue;
          const dx = b.x - a.x, dy = b.y - a.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          const force = (distance - 72) * .023;
          forces.get(edge.source).x += dx / distance * force;
          forces.get(edge.source).y += dy / distance * force;
          forces.get(edge.target).x -= dx / distance * force;
          forces.get(edge.target).y -= dy / distance * force;
        }
        for (const node of nodes) {
          const point = points.get(node.id), force = forces.get(node.id);
          point.x = Math.max(24, Math.min(width - 24, point.x + force.x + (centerX - point.x) * .004));
          point.y = Math.max(22, Math.min(height - 25, point.y + force.y + (centerY - point.y) * .004));
        }
      }
      return points;
    }

    function normalizePositions(points, nodes, width, height, marginX = 32, marginY = 30) {
      if (nodes.length === 1) return new Map([[nodes[0].id, {x:width / 2, y:height / 2}]]);
      const values = nodes.map(node => points.get(node.id)).filter(Boolean);
      const minX = Math.min(...values.map(point => point.x));
      const maxX = Math.max(...values.map(point => point.x));
      const minY = Math.min(...values.map(point => point.y));
      const maxY = Math.max(...values.map(point => point.y));
      const rangeX = Math.max(1, maxX - minX), rangeY = Math.max(1, maxY - minY);
      const scale = Math.min((width - marginX * 2) / rangeX, (height - marginY * 2) / rangeY);
      const sourceCenterX = (minX + maxX) / 2, sourceCenterY = (minY + maxY) / 2;
      return new Map(nodes.map(node => {
        const point = points.get(node.id);
        return [node.id, {
          x:width / 2 + (point.x - sourceCenterX) * scale,
          y:height / 2 + (point.y - sourceCenterY) * scale
        }];
      }));
    }

    function renderKnowledgeGraph({state, references, $, limit}) {
      const allNodes = state?.graph?.nodes || [];
      const allEdges = state?.graph?.edges || [];
      const focus = citationFocus({nodes:allNodes, edges:allEdges, references});
      const degree = new Map();
      allEdges.forEach(edge => [edge.source, edge.target].forEach(id => degree.set(id, (degree.get(id) || 0) + 1)));
      const stable = [...allNodes].sort((a, b) => String(a.id).localeCompare(String(b.id)));
      const priority = allNodes.length <= limit ? stable : stable.sort((a, b) =>
        Number(focus.cited.has(b.id)) - Number(focus.cited.has(a.id)) ||
        Number(focus.pathNodes.has(b.id)) - Number(focus.pathNodes.has(a.id)) ||
        (degree.get(b.id) || 0) - (degree.get(a.id) || 0) ||
        String(a.id).localeCompare(String(b.id))
      );
      const nodes = priority.slice(0, limit);
      const ids = new Set(nodes.map(node => node.id));
      const edges = allEdges.filter(edge => ids.has(edge.source) && ids.has(edge.target));
      $('#knowledge-graph-count').textContent = `${nodes.length}/${allNodes.length}`;
      $('#knowledge-graph-scope').textContent = allNodes.length > limit
        ? `전체 ${allNodes.length}개 중 ${nodes.length}개 표시 · 인용 문서와 실제 경로 우선`
        : `${allNodes.length}개 문서 모두 표시 · 실제 링크 ${allEdges.length}개`;
      if (!nodes.length) {
        $('#knowledge-graph').innerHTML = '<div class="knowledge-empty">위키 문서가 연결되면 전체 그래프가 여기에 표시됩니다.</div>';
        return;
      }

      const width = 340, height = 300;
      const layout = normalizePositions(positions(nodes, edges, width, height), nodes, width, height);
      const citationNumbers = new Map();
      for (const reference of references) {
        if (!citationNumbers.has(reference.id)) citationNumbers.set(reference.id, reference.number);
      }
      $('#knowledge-graph').innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="전체 위키 문서 그래프. 현재 답변이 인용한 문서가 강조됩니다.">${edges.map(edge => {
        const a = layout.get(edge.source), b = layout.get(edge.target);
        const highlighted = focus.pathEdges.has(edgeKey(edge.source, edge.target));
        return `<line class="knowledge-edge ${highlighted?'citation-path':''}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;
      }).join('')}${nodes.map(node => {
        const point = layout.get(node.id), cited = focus.cited.has(node.id), onPath = focus.pathNodes.has(node.id);
        const radius = cited ? 7 : Math.min(5, 3 + (degree.get(node.id) || 0) * .22);
        const number = citationNumbers.get(node.id);
        const fullLabel = number ? `[${number}] ${node.title}` : node.title;
        const label = fullLabel.length > 21 ? fullLabel.slice(0, 20) + '…' : fullLabel;
        return `<g class="knowledge-node ${cited?'cited':''} ${onPath&&!cited?'on-path':''}" data-page="${escapeHTML(node.id)}" role="button" tabindex="0" aria-label="${escapeHTML(cited?`참고문헌 ${number}, ${node.title} 열기`:`${node.title} 열기`)}" transform="translate(${point.x} ${point.y})"><circle r="${radius}"/><title>${escapeHTML(fullLabel)}</title>${cited?`<text y="${radius+13}">${escapeHTML(label)}</text>`:''}</g>`;
      }).join('')}</svg>`;
    }

    return {edgeKey, citationFocus, positions, normalizePositions, renderKnowledgeGraph};
  };
})(globalThis.WikiStudioModules = globalThis.WikiStudioModules || {});
