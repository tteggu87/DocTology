---
status: Active
source_of_truth: true
last_updated: 2026-09-06
superseded_by: N/A
---

# Architecture

DocTology is a local Wiki Studio application plus three reusable skills.

1. `runtime/` owns the Studio backend, launchers, and its adapter to the loop gates.
2. `dashboard/` owns the Studio static UI.
3. `.agents/skills/` contains exactly three distributable, self-contained skills.
4. `scripts/manage_skills.py` validates or copies only those skills.
5. `tests/` verifies the application and skills; Studio JavaScript evaluations live in `tests/dashboard/`.
6. `docs/`, `intelligence/`, and `wiki/` describe and remember this repository.

Generated wiki vaults are downstream products. Their Markdown is canonical and
optional SQLite is disposable. They receive neither the Studio application nor
loop gate executables.

`llm-wiki-loop` remains the authority for reusable procedure, coverage, batch,
receipt, seal, and certification gates. `runtime/wiki_loop_adapter.py` resolves
the repository loop skill root and calls that existing runtime against a target
vault. It does not reimplement gates or create another completion ledger.

The Studio runtime serves the repository-owned UI on localhost. Its chat
extension remains limited to root- and inventory-bound `wiki_list`,
`wiki_search`, `wiki_read`, and `wiki_links` reads; shell, write, external-web,
and ambient extension tools remain disabled. The existing loopback handshake,
root/origin/token checks, expected-root checks, browser-local history, bounded
read evidence, watcher opt-ins, conversation-preview limits, and writer
serialization remain unchanged. Studio operational state is not canonical wiki
state or completion authority.

Root `Wiki-Studio.command` and `Wiki-Studio.bat` are compatibility forwarders to
`runtime/start_dashboard.command` and `runtime/start_dashboard.bat`.
[ADR-0004](adr/ADR-0004-studio-runtime-separation.md) records the approved
migration. [Migration verification](evidence/2026-09-06-studio-runtime-separation.md) covers the current layout; previous skill-owned paths in historical evidence describe the old layout only.
