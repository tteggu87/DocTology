---
status: Active
source_of_truth: true
last_updated: 2026-08-26
superseded_by: N/A
---

# Current state

DocTology distributes exactly three skills: `llm-wiki-bootstrap`, `llm-wiki-loop`, and `repo-docs-intelligence-bootstrap`.

The canonical management entrypoint is `python3 scripts/manage_skills.py`. `check` validates the source inventory; `install` synchronizes it to a target skill root. Skill-owned scripts remain inside each skill and are copied with the skill.

The repository has no active ontology operator, root ontology pipeline, workbench, canonical corpus, or tracked archive. Optional SQLite in generated wiki vaults is derived retrieval state owned by `llm-wiki-bootstrap`.

Verification uses `python3 -m unittest discover -s tests` and the validator bundled in `repo-docs-intelligence-bootstrap`.

Repo Docs retrieval now separates cheap stat freshness, exact doctor verification,
and unchecked candidate discovery. Its Python fallback returns one best heading
chunk per document, supports one-connection `search-batch`, and checks Markdown
again immediately before atomic index publication. Optional POSIX and PowerShell
wrappers call native SQLite over shared search/traversal SQL without adding a
daemon. Rebuild includes a contentless trigram literal index by default;
`--no-trigram` retains compact token FTS for multi-gigabyte repositories.
SQLite builds without the trigram tokenizer fall back to that compact profile.

Generated LLM Wiki retrieval now uses the same operational split without copying
Repo Docs-specific trigram or native-wrapper policy: lexical search and bounded
wikilink traversal reuse one structural connection and return unchecked
candidates, `status` remains stat-based, and `doctor` remains content/vector
exact. Rebuilds stream page bodies, preserve compatible ONNX vectors in bounded
batches, correct peer-heading paths, and compare a streamed exact fingerprint
immediately before replacing the disposable index.

Generated wiki lint treats `_meta` navigation links and self-links as non-semantic for orphan detection. Orphans are advisory unless `lint --strict-orphans` is requested.

Generated workflow locks use `fcntl.flock` on Unix and `msvcrt.locking` on
Windows, preserving run-finalization and SQLite-refresh serialization without
adding a runtime dependency.
