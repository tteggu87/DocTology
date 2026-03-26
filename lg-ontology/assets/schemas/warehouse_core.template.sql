-- status: template
-- source_of_truth: no
-- schema_version: lightweight-ontology-core/v1
-- related_datasets: warehouse/jsonl/entities.jsonl, warehouse/jsonl/documents.jsonl, warehouse/jsonl/claims.jsonl, warehouse/jsonl/claim_evidence.jsonl, warehouse/jsonl/segments.jsonl, warehouse/jsonl/derived_edges.jsonl
-- authoritative_impl: scripts/sync_claims_to_duckdb.py

create table if not exists relations (
  relation_key varchar,
  label varchar,
  group_name varchar,
  payload_json varchar
);

create table if not exists document_types (
  document_type_key varchar,
  label varchar,
  default_claim_status varchar,
  payload_json varchar
);

create table if not exists entities (
  entity_id varchar,
  entity_type varchar,
  label varchar,
  status varchar,
  payload_json varchar
);

create table if not exists documents (
  document_id varchar,
  path varchar,
  document_type varchar,
  status varchar,
  payload_json varchar
);

create table if not exists claims (
  claim_id varchar,
  subject_id varchar,
  predicate varchar,
  object_id varchar,
  status varchar,
  review_state varchar,
  source_document_id varchar,
  payload_json varchar
);

create table if not exists claim_evidence (
  evidence_id varchar,
  claim_id varchar,
  source_document_id varchar,
  support varchar,
  payload_json varchar
);

create table if not exists segments (
  segment_id varchar,
  document_id varchar,
  document_type varchar,
  status varchar,
  ordinal bigint,
  payload_json varchar
);

create table if not exists derived_edges (
  edge_id varchar,
  source_claim_id varchar,
  rule_key varchar,
  subject_id varchar,
  predicate varchar,
  object_id varchar,
  status varchar,
  payload_json varchar
);

create table if not exists _mirror_meta (
  source_path varchar,
  source_hash varchar,
  row_count bigint,
  synced_at timestamp,
  schema_version varchar
);
