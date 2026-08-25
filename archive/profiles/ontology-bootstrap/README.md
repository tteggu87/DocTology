# Archived ontology bootstrap profiles

The `llm-first-ontology` and `wiki-plus-ontology` bootstrap profiles were removed
from the active `llm-wiki-bootstrap` CLI on 2026-08-25.

They combined a wiki bootstrap with canonical JSONL registries, `intelligence/`
contracts, proposal/review workflows, helper-model configuration, DuckDB helpers,
and ontology validators. That is a separate product boundary rather than a useful
first-run profile choice.

The last active implementation is preserved in Git history at commit `bb8420f`:

```bash
git show bb8420f:.agents/skills/llm-wiki-bootstrap/scripts/bootstrap_llm_wiki.py
```

New workspaces should use the active wiki-only bootstrap and independently choose
whether to enable its disposable SQLite retrieval index. Reintroducing ontology
materialization requires an explicit new product decision; it must not silently
return as a default profile.
