---
title: LLM Wiki loop runtime ownership verification
type: evidence
evidence_id: EVIDENCE-2026-08-27-LOOP-RUNTIME
date: 2026-08-27
subject: Standalone LLM Wiki loop runtime and bootstrap boundary
target_fingerprint: sha256:d49e04f8cb57ee71858c1b302d1508b4ab09526db4fa54a93dd50b66e98adf7c
related_decisions:
  - ../adr/ADR-0001-loop-runtime-ownership.md
related_plans: []
---

# EVIDENCE-2026-08-27-LOOP-RUNTIME: standalone loop runtime verification

## Claim And Scope

The LLM Wiki procedure, batch, and structural gates run from
`llm-wiki-loop`, while fresh bootstrap vaults contain no copied gate executable
or loop-only template. The loop can start a run against such a vault through
`--repo-root` without installing runtime code.

## Environment

- macOS, Python 3 standard-library runtime
- fresh temporary wiki-only vaults with SQLite both on and off
- target runtime files: bootstrap script and four loop runtime scripts

## Commands And Results

| Command | Result | Relevant output |
| --- | --- | --- |
| focused loop, batch, bootstrap, and distribution tests | pass | 44 tests, including lane-help forwarding edge cases, exact-target, nested-root rejection, standalone, no-install, and legacy-local-runtime cases |
| `python3 -m unittest discover -s tests` | pass | 166 tests |
| `python3 scripts/manage_skills.py check` | pass | exactly three self-contained skills |
| skill quick validation for bootstrap and loop | pass | both skill trees valid |
| fresh `--sqlite on` and `--sqlite off` bootstrap checks | pass | no copied loop scripts/assets; SQLite helper presence matches choice |

## Limitations

- Real-world semantic source synthesis remains LLM work; these checks validate
  procedure, structural boundaries, and runtime ownership only.
- Existing vaults may retain old repo-local gate files. The new loop reports but
  does not modify them.

## Target Binding

The target fingerprint is the combined SHA-256 of the bootstrap script and the
loop entrypoint, procedure, batch, and pipeline runtime scripts at verification
time.
