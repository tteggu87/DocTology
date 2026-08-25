# AGENTS.md

## Working style
- Plan first for non-trivial tasks.
- Search before code.
- Read durable repo memory before substantial work: `wiki/_meta/index.md`, `wiki/_meta/log.md`, and relevant `wiki/analyses/*`.
- From the memory index and recent log, follow relevant local Markdown links for at most 2 additional hops and at most 12 pages total; record the bounded reading path and verify linked canonical files before relying on wiki claims.
- Do impact analysis before modifying schemas, manifests, handlers, or graph/materialization code.
- Follow schema-first: define glossary/action/schema before adding implementation.
- Update the smallest canonical truth first when concepts, actions, or boundaries change.
- Treat drift between code, docs, contracts, wiki memory, and guidance as a bug to resolve or record in the same task.
- Run the repository-local validator with `python scripts/validate_repo_docs_intelligence.py --repo-root .` when it exists; otherwise use the bundled skill validator from the installed `repo-docs-intelligence-bootstrap` skill.
- Before declaring structural repo-docs work complete, run the validator after the last mutation with an exact changed-file list and `--finalize`; use `--verify-finalized` to detect a stale `state/repo_docs_finalize.json` receipt.
- Keep YAML for meaning/contracts, SQL for schema/materialization, policy files for gates/rules, and Python for execution only.

## Repository rules
- Treat live code and registered entrypoints as truth for what runs.
- Treat current docs as human-readable truth only when they match live code and registered contracts.
- Treat intelligence manifests as reusable machine-readable contracts when present.
- Treat generated indexes, search outputs, graph projections, and wiki memory as derived aids unless this repository explicitly defines them as canonical.
- Use this authority order when artifacts disagree: live code and tests; current canonical docs and accepted ADRs; intelligence contracts; plans, evidence, and reviews; derived wiki memory; optional search indexes.
- Prefer thin wrappers and a thick core package.
- Keep repository memory lightweight; add docs, contracts, or wiki pages only when they reduce ambiguity, drift, or repeated mistakes.
- Keep `wiki/` as derived memory for analyses, source notes, plans, reviews, and cross-session context; do not treat wiki pages as runtime truth.
- Keep decision status separate from implementation status. A plan does not prove delivery, evidence does not replace current docs, and a wiki decision does not replace its canonical ADR or decision source.
- Create nested `AGENTS.md` only for a distinct operational root with its own build, test, deploy, or safety rules.

## Documentation rules
- Do not delete old docs unless clearly obsolete and duplicated.
- Move outdated docs to `docs/archive/` with a status banner.
- Keep current-state docs aligned with actual code.
- Distinguish current truth, intentional legacy, and unresolved drift explicitly.
- Keep `wiki/_meta/index.md` and `wiki/_meta/log.md` current after meaningful repo-docs maintenance.
- Use descriptive relative Markdown links in new or materially rewritten Repo Docs wiki pages so links to docs, intelligence, code, and tests remain precise and portable. Continue to read existing Obsidian `[[wikilinks]]`, but do not introduce them as the Repo Docs default or mass-convert legacy pages solely for syntax consistency.
- Save reusable plan reviews, drift analyses, source comparisons, and decision memos under `wiki/analyses/`.
- Include source, assumption, conflict, and evidence-confidence notes when preserving claim-heavy analysis.
- Promote documentation only when warranted: use canonical docs plus impact/log for small changes, `wiki/analyses/` for reusable analysis, an ADR for durable structural or compatibility decisions, a plan for multi-stage work, evidence for verification claims, and a review for scoped review findings.
- Do not pre-create optional ADR, plan, evidence, review, decision, or repo-map directories. New repositories may default to `docs/adr/`; preserve existing flat or custom ADR locations without migration or key renaming.
- Keep wiki decisions explicitly `source_of_truth: false` and link each one to its canonical ADR or canonical decision source.

## Change synchronization rules

When code changes, update the corresponding docs and intelligence artifacts in the same task.

You must check whether these files need updates:
- `docs/CURRENT_STATE.md` when behavior, entrypoints, providers, defaults, or runtime flow changes
- `docs/ARCHITECTURE.md` when component roles, data flow, or storage responsibilities change
- `docs/LAYERS.md` when boundaries between Raw/Core/Derived/Search/Graph/Serve change
- `docs/repo-map/ENTRYPOINTS.md` when entrypoints, scripts, routes, or wrappers change and a repo-map exists
- `docs/repo-map/MODULES.md` and `docs/repo-map/SYMBOL_GRAPH.md` when broad module ownership or high-impact symbols change and a repo-map exists
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
- the active ADR location when a durable structural, authority, or compatibility decision changes
- `docs/plans/*.md` when multi-stage scope or the current next action changes
- `docs/evidence/*.md` when a performance, security, compatibility, or completion claim changes
- `docs/reviews/*.md` when a review target, finding, or disposition changes
- `wiki/decisions/*.md` when a derived decision summary needs to track its canonical source

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
- The final validator gate is warning-free, its changed-file list matches current Git state when available, and its receipt is bound to the latest listed file contents.
