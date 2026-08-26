WITH RECURSIVE
normalized(value) AS (
  SELECT trim(replace(replace(replace(:query, char(9), ' '), char(10), ' '), char(13), ' '))
), terms(rest, token) AS (
  SELECT (SELECT value FROM normalized) || ' ', ''
  UNION ALL
  SELECT ltrim(substr(rest, instr(rest, ' ') + 1)),
         substr(rest, 1, instr(rest, ' ') - 1)
  FROM terms
  WHERE rest <> ''
), term_query(value) AS (
  SELECT group_concat('"' || replace(token, '"', '""') || '"', ' AND ')
  FROM terms
  WHERE token <> ''
), settings(schema_ok, trigram_enabled) AS (
  SELECT
    EXISTS(
      SELECT 1 FROM index_metadata
      WHERE key = 'schema_version' AND value = 'repo-docs-heading-index-v3'
    ),
    EXISTS(
    SELECT 1 FROM index_metadata
    WHERE key = 'trigram_index' AND value = 'enabled'
  )
), matched AS (
  SELECT c.document_path, d.title, c.heading_path, c.line_start, c.line_end,
         c.content, c.chunk_index, bm25(chunk_trigram) AS score
  FROM chunk_trigram
  JOIN chunks c ON c.rowid = chunk_trigram.rowid
  JOIN documents d ON d.path = c.document_path
  WHERE :mode = 'literal' AND length(:query) >= 3
    AND (SELECT trigram_enabled FROM settings)
    AND chunk_trigram MATCH ('"' || replace(:query, '"', '""') || '"')
  UNION ALL
  SELECT c.document_path, d.title, c.heading_path, c.line_start, c.line_end,
         c.content, c.chunk_index, bm25(chunk_fts) AS score
  FROM chunk_fts
  JOIN chunks c ON c.id = chunk_fts.chunk_id
  JOIN documents d ON d.path = c.document_path
  WHERE :mode = 'literal'
    AND (length(:query) < 3 OR NOT (SELECT trigram_enabled FROM settings))
    AND chunk_fts MATCH (
      CASE WHEN length(:query) < 3
        THEN '"' || replace(:query, '"', '""') || '"*'
        ELSE '"' || replace(:query, '"', '""') || '"'
      END
    )
  UNION ALL
  SELECT c.document_path, d.title, c.heading_path, c.line_start, c.line_end,
         c.content, c.chunk_index, bm25(chunk_fts) AS score
  FROM chunk_fts
  JOIN chunks c ON c.id = chunk_fts.chunk_id
  JOIN documents d ON d.path = c.document_path
  WHERE :mode = 'terms'
    AND chunk_fts MATCH (SELECT value FROM term_query)
), ranked AS (
  SELECT *, row_number() OVER (
    PARTITION BY document_path ORDER BY score, chunk_index
  ) AS document_rank
  FROM matched
), limited AS (
  SELECT * FROM ranked
  WHERE document_rank = 1
  ORDER BY score, document_path
  LIMIT :limit
)
SELECT CASE WHEN NOT (SELECT schema_ok FROM settings) THEN json_object(
    'error', 'derived retrieval index schema is incompatible; run rebuild',
    'freshness', 'unchecked',
    'canonical', json('false')
  ) ELSE json_object(
    'query', :query,
    'results', json(COALESCE(json_group_array(json_object(
      'path', document_path,
      'title', title,
      'heading_path', heading_path,
      'line_start', line_start,
      'line_end', line_end,
      'score', score,
      'snippet', substr(content, 1, 320)
    )), '[]')),
    'freshness', 'unchecked',
    'canonical', json('false')
  ) END
FROM limited;
