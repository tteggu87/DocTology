# AGENTS.md

## Working style
- Plan first for non-trivial tasks.
- Search before code.
- Read durable repo memory before substantial work: `wiki/_meta/index.md`, `wiki/_meta/log.md`, and relevant `wiki/analyses/*`.
- Do impact analysis before modifying schemas, manifests, handlers, or graph/materialization code.
- Follow schema-first: define glossary/action/schema before adding implementation.
- Update the smallest canonical truth first when concepts, actions, or boundaries change.
- Treat drift between code, docs, contracts, wiki memory, and guidance as a bug to resolve or record in the same task.
- Run `python scripts/validate_repo_docs_intelligence.py --repo-root .` when the validator is available.
- Keep YAML for meaning/contracts, SQL for schema/materialization, policy files for gates/rules, and Python for execution only.

## Repository rules
- Treat the layered ontology store as canonical truth.
- Treat graph traversal as sidecar behavior, not source of truth.
- Do not mix search signal with ontology truth.
- Prefer thin wrappers and a thick core package.
- Keep the ontology lightweight; add artifacts only when they reduce ambiguity, drift, or repeated mistakes.
- Keep `wiki/` as derived memory for analyses, source notes, plans, reviews, and cross-session context; do not treat wiki pages as runtime truth.
- Create nested `AGENTS.md` only for a distinct operational root with its own build, test, deploy, or safety rules.

## Documentation rules
- Do not delete old docs unless clearly obsolete and duplicated.
- Move outdated docs to `docs/archive/` with a status banner.
- Keep current-state docs aligned with actual code.
- Distinguish current truth, intentional legacy, and unresolved drift explicitly.
- Keep `wiki/_meta/index.md` and `wiki/_meta/log.md` current after meaningful repo-docs maintenance.
- Save reusable plan reviews, drift analyses, source comparisons, and decision memos under `wiki/analyses/`.
- Include source, assumption, conflict, and evidence-confidence notes when preserving claim-heavy analysis.

## Change synchronization rules

When code changes, update the corresponding docs and intelligence artifacts in the same task.

You must check whether these files need updates:
- `docs/CURRENT_STATE.md` when behavior, entrypoints, providers, defaults, or runtime flow changes
- `docs/ARCHITECTURE.md` when component roles, data flow, or storage responsibilities change
- `docs/LAYERS.md` when boundaries between Raw/Core/Derived/Search/Graph/Serve change
- `docs/SKILLS_INTEGRATION.md` when CLI, skill wrappers, or external entrypoints change
- `docs/ROADMAP.md` when deferred cleanup or staged alignment changes
- `docs/IMPACT_SUMMARY.md` when structural changes or validator findings need explicit reporting
- `intelligence/glossary.yaml` when a new domain term or canonical concept is introduced or renamed
- `intelligence/manifests/actions.yaml` when an action is added, removed, renamed, or its contract changes
- `intelligence/manifests/entities.yaml` when canonical entities change
- `intelligence/manifests/datasets.yaml` when canonical datasets or shapes change
- `intelligence/handlers/*.yaml` when event chains or orchestration flow changes
- `intelligence/policies/*.yaml` when gate/policy/rule semantics change
- `intelligence/registry/capabilities.yaml` when Python capability bindings change
- `intelligence/schemas/*.sql` when canonical schema, views, or materialization logic changes
- `AGENTS.md` when working rules or repo guidance drift from actual practice
- `wiki/_meta/index.md` when wiki page inventory or reading routes change
- `wiki/_meta/log.md` when meaningful repo-docs maintenance occurs
- `wiki/analyses/*.md` when the task produced reusable reasoning, decisions, rejected alternatives, or unresolved conflicts

Before finishing, report:
1. which docs/intelligence files were updated
2. which were checked but did not need changes
3. which wiki memory files were updated or intentionally left unchanged
4. any remaining drift or legacy exceptions
5. whether the change introduced any new canonical terms, actions, handlers, policies, datasets, or schema contracts
6. validator errors or warnings, or why the validator was not run

## Done when
- File changes match real code behavior.
- Docs are updated when architecture or entrypoints change.
- Contracts and capability bindings stay aligned with implementation.
- Durable reasoning is preserved in wiki memory when it will help future sessions.
- Impact summary is written for structural changes.
- Validator failures are resolved before reporting success.
