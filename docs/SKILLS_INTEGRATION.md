---
status: Active
source_of_truth: true
last_updated: 2026-08-26
superseded_by: N/A
---

# Skills integration

Use `llm-wiki-bootstrap` once to create a wiki and choose SQLite on or off. Use `llm-wiki-loop` for repeated source-to-wiki growth and certification. Use `repo-docs-intelligence-bootstrap` for code repositories whose docs and durable working context must evolve with implementation.

Install all three with `python3 scripts/manage_skills.py install`. Copying only a `SKILL.md` is unsupported because bootstrap and Repo Docs depend on sibling scripts, assets, references, or eval fixtures.

The wiki skills use Obsidian wikilinks inside generated vaults. Repo Docs memory uses portable relative Markdown links.

Repo Docs carries five cooperating retrieval files: the portable Python owner,
POSIX and PowerShell native SQLite readers, and shared search/traversal SQL.
Agents run cheap `status` before substantial discovery, use unchecked search or
traversal only to choose Markdown to open, and reserve exact hashing/integrity
proof for `doctor`. Default trigram literal indexing can be disabled at rebuild
time with `--no-trigram` for storage-sensitive multi-gigabyte corpora.
