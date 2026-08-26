WITH RECURSIVE settings(schema_ok) AS (
  SELECT EXISTS(
    SELECT 1 FROM index_metadata
    WHERE key = 'schema_version' AND value = 'repo-docs-heading-index-v3'
  )
), starting AS (
  SELECT path, title
  FROM documents
  WHERE (path = :start OR lower(title) = lower(:start))
    AND (SELECT schema_ok FROM settings)
  ORDER BY path
  LIMIT 2
), walk(path, title, label, depth, visited, route_order) AS (
  SELECT path, title, '', 0, char(31) || path || char(31), ''
  FROM starting
  WHERE (SELECT count(*) FROM starting) = 1
  UNION ALL
  SELECT d.path, d.title, l.label, walk.depth + 1,
         walk.visited || d.path || char(31),
         walk.route_order || char(31) || d.path
  FROM walk
  JOIN markdown_links l ON l.source_path = walk.path AND l.status = 'resolved'
  JOIN documents d ON d.path = l.target_path
  WHERE walk.depth < :hops
    AND instr(walk.visited, char(31) || d.path || char(31)) = 0
), ranked AS (
  SELECT *, row_number() OVER (
    PARTITION BY path ORDER BY depth, route_order
  ) AS document_rank
  FROM walk
  WHERE depth > 0
), limited AS (
  SELECT * FROM ranked
  WHERE document_rank = 1
  ORDER BY depth, route_order
  LIMIT :limit
)
SELECT CASE
  WHEN NOT (SELECT schema_ok FROM settings) THEN json_object(
    'error', 'derived retrieval index schema is incompatible; run rebuild',
    'freshness', 'unchecked',
    'canonical', json('false')
  )
  WHEN (SELECT count(*) FROM starting) != 1 THEN json_object(
    'error', 'start document is missing or ambiguous',
    'freshness', 'unchecked',
    'canonical', json('false')
  )
  ELSE json_object(
    'start', (SELECT path FROM starting),
    'hops', :hops,
    'limit', :limit,
    'results', json(COALESCE((SELECT json_group_array(json_object(
      'path', path,
      'title', title,
      'label', label,
      'depth', depth
    )) FROM limited), '[]')),
    'freshness', 'unchecked',
    'canonical', json('false')
  )
END;
