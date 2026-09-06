---
status: Active
source_of_truth: true
last_updated: 2026-08-27
superseded_by: N/A
---

# Documentation portal

- [Current state](CURRENT_STATE.md)
- [Architecture](ARCHITECTURE.md)
- [Layer boundaries](LAYERS.md)
- [Skill integration](SKILLS_INTEGRATION.md)
- [Roadmap](ROADMAP.md)
- [Impact summary](IMPACT_SUMMARY.md)
- [Repository map](repo-map/README.md)
- [ADR index](adr/README.md), including [loop runtime ownership](adr/ADR-0001-loop-runtime-ownership.md); [plans](plans/README.md), [evidence](evidence/README.md), [reviews](reviews/README.md), [archive](archive/README.md)
- [Derived decision memory](../wiki/decisions/README.md)
- [Repo Docs retrieval absorption evidence](evidence/2026-08-26-repo-docs-sqlite-absorption.md)

DocTology's current product boundary is the repository-owned Wiki Studio application (`runtime/` and `dashboard/`) plus the three reusable directories under `.agents/skills/`. `manage_skills` installs only the skills. Repository memory is derived context and does not override those sources.

- [Local Wiki Studio usage](../dashboard/README.md)
- [Studio runtime separation](adr/ADR-0004-studio-runtime-separation.md) and [migration verification](evidence/2026-09-06-studio-runtime-separation.md); [parallel preparation decision](adr/ADR-0003-wiki-parallel-preparation.md), [completed implementation plan](plans/2026-09-05-wiki-parallel-preparation.md), [verification](evidence/2026-09-06-wiki-parallel-preparation.md), and [review](reviews/2026-09-06-wiki-parallel-preparation.md)

- [Wiki Studio 인수인계 위키](../wiki/decisions/local-wiki-studio.md)
