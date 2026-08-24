# Claim Lifecycle

## Purpose

This document defines the minimum operational lifecycle for claims in `lightweight-ontology-core`.

## Status Values

- `proposed`: extracted or authored, not yet approved
- `accepted`: approved by a human reviewer and eligible for derivation
- `disputed`: conflict is open and unresolved
- `rejected`: explicitly denied or invalid
- `superseded`: replaced by a newer accepted claim

## Review State Pairing

Use only these combinations:

- `proposed + needs_review`
- `accepted + approved`
- `disputed + conflict_open`
- `rejected + rejected`
- `superseded + archived`

## Accepted Claim Requirements

An accepted claim must include:

- `reviewed_by`
- `reviewed_at`
- `decision_by`
- `decision_at`
- `decision_note`
- at least one supporting evidence row

If segment references are present, accepted claims and their evidence should point to stable IDs in `warehouse/jsonl/segments.jsonl`.

`decision_by` must use a human identifier convention such as `human:<id>`.

## Validation Intent

The validator should reject:

- accepted claims without supporting evidence
- accepted claims without review metadata
- proposed claims marked as approved
- derived edges sourced from anything other than accepted claims
