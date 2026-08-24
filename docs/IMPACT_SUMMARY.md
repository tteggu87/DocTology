# Impact Summary

Updated: 2026-05-08

## Repository analysis summary

- The repo already had partial alignment across `README.md`, `AGENTS.md`, `docs/CURRENT_STATE.md`, and the live Python runtime.
- The biggest gap was not architecture ambiguity inside code; it was missing durable docs around current entrypoints, layer boundaries, and the minimal intelligence contract.
- The workbench split is transitional but real: `scripts/workbench_api.py` is still live while `scripts/workbench/` contains the thicker implementation.
- The closed ingest gap is now documented explicitly: source registration is not the same as a completed ontology-backed ingest lifecycle.
- The closed ingest contract is now propagated to repo-local `AGENTS.md`, public READMEs, checked-in skills, and bootstrap-generated ontology starter files.
- The configured full ingest path now exists: `scripts/llm_full_ingest.py --apply` closes source page, affected wiki page, proposed JSONL, index/log, and report artifacts without accepted-truth automation.

## Docs structure changes

Updated:

- `docs/README.md`
- `docs/CURRENT_STATE.md`
- `docs/ARCHITECTURE.md`
- `docs/LAYERS.md`
- `docs/SKILLS_INTEGRATION.md`
- `docs/ROADMAP.md`
- `docs/IMPACT_SUMMARY.md`

Created:

- `docs/CLOSED_INGEST_PIPELINE.md`

Checked and left unchanged:

- `scripts/incremental_ingest.py`
- `scripts/incremental_support.py`
- `scripts/workbench/*.py`

Also updated outside `docs/`:

- `AGENTS.md`
- `README.md`
- `README.ko.md`
- `scripts/llm_wiki.py`
- `scripts/llm_full_ingest.py`
- `scripts/pipeline_check.py`
- `.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py`
- `.agents/skills/llm-wiki-loop/SKILL.md`
- `.agents/skills/llm-wiki-loop/references/ontology-contract.md`
- `archive/skills/README.md`
- `archive/skills/lightweight-ontology-core/`
- `archive/skills/lg-ontology/`
- `.agents/skills/ontology-pipeline-operator/SKILL.md`
- `tests/test_llm_wiki_pipeline_contract.py`
- `tests/test_llm_full_ingest_runtime.py`
- `tests/test_pipeline_check.py`

## Intelligence layer changes

Updated:

- `intelligence/glossary.yaml`
- `intelligence/manifests/actions.yaml`
- `intelligence/manifests/datasets.yaml`
- `intelligence/policies/truth-boundaries.yaml`

Created:

- `intelligence/manifests/pipelines.yaml`

Checked and left unchanged:

- `intelligence/manifests/source_families.yaml`
- `intelligence/manifests/workbench.yaml`
- `intelligence/manifests/entities.yaml`
- `intelligence/registry/capabilities.yaml`

## Legacy vs current split

- Current canonical local entrypoints:
  - `scripts/llm_wiki.py`
  - `scripts/incremental_ingest.py`
  - `scripts/workbench/server.py` plus `scripts/workbench/repository.py` as the workbench core
- Intentional legacy/transitional support:
  - `scripts/workbench_api.py` remains a live compatibility wrapper and should not be archived as dead

## Drift resolved

- Missing docs portal pages for architecture, layers, skills integration, roadmap, and impact reporting
- Missing intelligence artifacts for named runtime surfaces, capability bindings, and explicit truth/mutation policies
- Missing action contracts for current workbench query-preview, save-analysis, review-claim, and maintenance flows
- Missing explicit closed-ingest distinction between source registration, proposed JSONL appends, wiki projection, meta refresh, structural validation, and reporting
- Missing propagation of the closed-ingest contract into the primary agent/skill/bootstrap surfaces
- Previously missing executable configured-LLM growth loop beyond source-page-only projection

## Remaining drift

- There is still no repo-local validator such as `scripts/validate_repo_docs_intelligence.py`
- `scripts/pipeline_check.py` exists, but it remains structural and should not be treated as semantic truth validation
- `docs/` reflects current runtime truth, but future route or adapter growth will need follow-up updates
- The intelligence layer remains intentionally minimal and does not yet document every workbench route as a first-class entity
- Accepted-truth promotion remains a separate future review workflow

## Validator status

- No dedicated docs/intelligence validator script exists in this repository, so manual drift checks are still required
- Manual drift verification should continue to compare `AGENTS.md`, `docs/`, `intelligence/`, `scripts/`, and tests together
- Unit-test verification should include the full ingest and pipeline-check tests

## Cautions

- Do not promote `scripts/workbench_api.py` to the primary workbench truth surface; it is a live wrapper, not the thicker core
- Do not let browser flows mutate `raw/` or broad canonical registries directly
- Do not expand the intelligence layer just for completeness; add only contracts that reduce real ambiguity
- Do not turn `intelligence/manifests/pipelines.yaml` into a manifest executor or semantic router
- Do not report `scripts/llm_wiki.py ingest` registration-only output as completed ontology-backed ingest
