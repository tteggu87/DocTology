---
status: Active
source_of_truth: false
last_updated: 2026-09-06
superseded_by: N/A
---

# Entrypoints

- Canonical repository command: `python3 scripts/manage_skills.py check|install`; it validates and installs exactly the three reusable skills.
- Studio backend: `runtime/wiki_dashboard.py [--repo-root <vault>] [--port <available-port>]` serves the repository-owned UI and isolated read-only Pi RPC adapter.
- Studio gate binding: `runtime/wiki_loop_adapter.py` resolves the repository loop skill root and delegates to its unchanged `wiki_loop.py` gates.
- Studio launchers: `runtime/start_dashboard.command` and `runtime/start_dashboard.bat`; root `Wiki-Studio.command` and `Wiki-Studio.bat` are thin compatibility forwarders.
- Skill entrypoints: each retained `.agents/skills/*/SKILL.md` and its documented sibling scripts.
- Standalone LLM Wiki loop gates: `llm-wiki-loop/scripts/wiki_loop.py --repo-root <vault> preflight|workflow|batch|check` runs reusable gates without copying executables into the vault.
- Verification: `python3 -m unittest discover -s tests` and the bundled Repo Docs validator.

The Studio retains the authenticated loopback handshake and root-bound source
entry routes. Its read-only chat has no shell, write, or external-web tools.
Gate behavior remains owned by the loop skill. These paths are covered by [migration verification](../evidence/2026-09-06-studio-runtime-separation.md) and [ADR-0004](../adr/ADR-0004-studio-runtime-separation.md).
