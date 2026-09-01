---
status: Active
source_of_truth: true
last_updated: 2026-09-01
superseded_by: N/A
---

# Skills integration

Use `llm-wiki-bootstrap` once to create a wiki and choose SQLite on or off. Use
`llm-wiki-loop` for repeated source-to-wiki growth and certification. Its gate
runtime stays inside the loop skill and operates a target through `--repo-root`;
it does not install gate executables in the target. Use
`repo-docs-intelligence-bootstrap` for code repositories whose docs and durable
working context must evolve with implementation.

For multi-source wiki growth, keep every linked run at its pre-mutation boundary
while workers stage drafts, apply one merged writer result, record current
question receipts, and invoke `batch seal`. The seal writes review and run state
outside `wiki/`, performs one optional retrieval refresh, and certifies the same
unchanged corpus snapshot.

Install all three with `python3 scripts/manage_skills.py install`. Copying only a `SKILL.md` is unsupported because bootstrap and Repo Docs depend on sibling scripts, assets, references, or eval fixtures.

The wiki skills use Obsidian wikilinks inside generated vaults. Repo Docs memory uses portable relative Markdown links.

SQLite-enabled wiki vaults expose raw heading `tree`, `ancestors`, and `subtree`
queries as optional planning aids. `llm-wiki-loop` reopens canonical Markdown
before synthesis and reads Markdown directly when derived structure is off,
unavailable, or stale. Tree leaves never become a second coverage ledger.

Repo Docs carries five cooperating retrieval files: the portable Python owner,
POSIX and PowerShell native SQLite readers, and shared search/traversal SQL.
Agents run cheap `status` before substantial discovery, use unchecked search or
traversal only to choose Markdown to open, and reserve exact hashing/integrity
proof for `doctor`. Default trigram literal indexing can be disabled at rebuild
time with `--no-trigram` for storage-sensitive multi-gigabyte corpora.
