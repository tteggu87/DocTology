# Comparison Workflow

Use this workflow before deciding that a graph layer is worth keeping.

## Goal

Compare direct canonical lookup against graph-style neighborhood expansion for the same seed entity or label.

## Recommended Steps

1. Validate the ontology core.
2. Export the graph projection.
3. Run `compare_graph_modes.py` with a representative seed query.
4. Check whether graph mode reveals materially useful extra context.
5. Only then decide whether Ladybug is justified.

## What To Look For

- extra reachable entities that matter
- clearer provenance chains
- easier path explanation
- useful multi-hop context that direct lookup missed

## What Not To Overclaim

- more nodes does not mean better answers
- denser graphs do not prove higher quality
- graph traversal does not replace claim review

## Good Seed Queries

- exact entity id such as `svc.api`
- exact entity label such as `Public API Service`
- central concept labels in educational material
- focal company or metric identifiers in finance notes

## Decision Rule

Keep the graph layer only if the extra context is meaningfully helpful for:

- explanation
- exploration
- graph-assisted context assembly

If the result is only cosmetic, stay with the core workflow.
