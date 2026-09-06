# DocTology agent contract

DocTology distributes exactly three reusable skills:

- `.agents/skills/llm-wiki-bootstrap`
- `.agents/skills/llm-wiki-loop`
- `.agents/skills/repo-docs-intelligence-bootstrap`

## Working rules

1. Treat each skill directory as a self-contained product. Keep its scripts, assets, references, and evals beside `SKILL.md`.
2. Do not add an active ontology profile, workbench, or corpus. DocTology owns the single Studio runtime in `runtime/` and UI in `dashboard/`; do not copy Studio application files into a reusable skill or a generated vault. `llm-wiki-loop` owns gates only.
3. Keep `scripts/manage_skills.py` thin: it validates and installs only the three source skill directories.
4. Update affected tests and current docs in the same change.
5. Use relative Markdown links in repository docs. Obsidian wikilinks belong to vaults created by `llm-wiki-bootstrap`.
6. Derived SQLite indexes belong to generated vaults or local `state/`; they are disposable, never canonical truth.
7. Historical implementations remain recoverable from Git history and `archive/branches/*` tags, not an active `archive/` tree.

## Reading order

Read [the documentation portal](docs/README.md), then [current state](docs/CURRENT_STATE.md), then the relevant skill's `SKILL.md`. Use [the repo map](docs/repo-map/README.md) for entrypoints and data flow.

## Definition of done

- `python3 scripts/manage_skills.py check` passes.
- `python3 -m unittest discover -s tests` passes.
- Repo Docs validation has no errors or warnings.
- The global install is synchronized when requested.
- Current docs and `wiki/_meta/log.md` reflect meaningful structural changes.

## CodeGraph

When `.codegraph/` exists, use `codegraph explore` before broad text search for code-structure questions.
