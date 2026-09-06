---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Wiki Studio maintainability refactor

Understood as: preserve the current dashboard's behavior and visual layout while separating responsibilities and making feature changes independently testable. This is not a redesign, new retrieval engine, or orchestration rewrite.

## Frozen boundaries

- Historical pre-migration plan observation: the loop skill was the only dashboard owner. No build dependency or fourth product. Superseded ownership is recorded in [ADR-0004](../adr/ADR-0004-studio-runtime-separation.md).
- Existing writer, batch, coverage, and certification gates remain authoritative.
- Chat, source workers, root/Origin/token validation, model defaults, opt-in watching, and explicit recovery keep their current contracts.
- Existing browser history and user-vault files must be preserved.
- The existing uncommitted implementation is baseline work, not disposable output.

## Structural changes

1. Separate document inventory/evidence/snapshot operations into a dependency-injected catalog and native/local folder selection into its own module.
2. Separate HTTP transport and static asset admission from application orchestration. Keep a narrow compatible Python entrypoint.
3. Separate frontend feature logic through explicit dependencies and one production loading order, shared by browser and contract tests. Avoid implicit new global application state or a framework/build migration.
4. Add module/asset boundary checks, retain existing behavior regressions, and verify the current browser build.

## Completion checks

- Existing behavioral tests retained and passing, plus independent module and cold-load coverage.
- No canonical user-vault mutations or model invocation required for refactoring QA.
- Distribution validation, documentation validation, whitespace check, and live browser verification pass.
- Current docs describe where extensions belong and which boundaries must not be crossed.

## Outcome

Completed: backend composition/catalog/folder/HTTP separation; five explicit-input frontend factories; external single boot and HTML-driven asset admission; independent module, HTTP, and cold-load checks. Python 385 and JavaScript 134 passed. Browser verification preserved the current layout, history, graph, reader, status, and folder browser. See the [verification record](../evidence/2026-09-06-dashboard-refactor.md) for repairs, limits, and local deployment.
