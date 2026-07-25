# Three-Layer LLM Wiki Taxonomy

This reference freezes the top-level semantic object split for a file-first LLM Wiki with SQLite and DuckDB support.

## Object classes

### Source

- original evidence-bearing artifact
- closest layer to final evidence
- examples: raw web clip, transcript, PDF text, note, chat log

### Claim

- extracted or curated proposition from source material
- must carry provenance and confidence

### Page

- maintained synthesis surface for humans and agents
- readable working surface
- not the same thing as source truth

### Relation

- link between entity, page, claim, or source
- should begin weak and become stronger only when justified

### Memory

- user preference, operational state, working context, or agent continuity state
- must remain separate from canonical knowledge truth

## Ownership summary

- files own canonical truth
- SQLite owns operational index state only
- DuckDB owns analytical state only

## Rules

1. page != claim
2. source != page
3. relation != page body
4. memory != canonical truth
5. DB layers must remain rebuildable from canonical file-layer inputs
