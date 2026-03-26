# Repo Adapter Boundary

## What The Core Skill Owns

`lightweight-ontology-core` owns:

- relation and document-type vocabularies
- canonical entities/documents/claims/evidence registries
- canonical segment registries for retrieval and provenance
- derived edge materialization
- provenance-aware validation
- DuckDB mirror synchronization
- retrieval configuration and Chroma index synchronization

## What The Repo Skill Owns

`repo-docs-intelligence-bootstrap` owns:

- `CURRENT_STATE`, `ARCHITECTURE`, `LAYERS`, `AGENTS`, and portal docs
- current vs legacy repo truth management
- same-task anti-drift synchronization for repo documentation and manifests
- repo-facing validators and fixture repos

## Composition Rule

Compose, do not merge.

- Repo adapter work may reference or generate claim/evidence/segment data using the core patterns.
- The core skill should not absorb repo-only trigger phrases like plain docs refresh or AGENTS sync.
- The repo skill should not become a generic ontology extraction skill.

## Future Integration Direction

A future repo adapter may:

- populate core JSONL registries from repo docs
- materialize dependency or documentation edges
- call both validators in sequence
- use Chroma-backed segment recall without changing ontology truth ownership

But the trigger surfaces should remain separate.
