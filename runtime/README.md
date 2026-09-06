# DocTology runtime

This directory owns the local application: HTTP, workspace connection, document discovery, Pi chat, source intake, worker supervision, process lifetime, and desktop startup. The browser UI lives in [dashboard/](../dashboard/README.md).

```text
Wiki-Studio.command / Wiki-Studio.bat
  -> runtime/start_dashboard.command / start_dashboard.bat
  -> runtime/wiki_dashboard.py
       -> dashboard/ (declared static assets)
       -> wiki_loop_adapter.py
            -> .agents/skills/llm-wiki-loop (existing gate implementation)
```

## Run

From the repository root:

```bash
python3 runtime/wiki_dashboard.py
python3 runtime/wiki_dashboard.py --repo-root /absolute/path/to/wiki --open-browser
```

The first command shows a labelled unconnected example. The root desktop launchers add browser opening and bounded free-port selection. Python 3.11+ is required; Pi installation/authentication is needed for model work. See the [desktop guide](../dashboard/README.md#더블클릭으로-실행) for prerequisites, shutdown, and platform limits.

## Ownership boundary

- `wiki_loop_adapter.py` is the single repository-relative binding to the loop skill. The server, writer prompts, and explicit Pi skill selection use its paths. No gate code is copied here.
- The loop skill owns synthesis procedure, source/batch records, coverage checks, and certification. It does not import or distribute this application.
- The runtime coordinates work and displays existing evidence. Worker drafts, process exits, chat answers, and queue labels never replace the original completion gates.
- Chat tools/extensions and parallel preparation supervision belong here because they are application behavior. A single canonical writer and separate read-only chat lane remain in force.
- `scripts/manage_skills.py install` distributes only the three reusable skills, not `runtime/` or `dashboard/`. Running Wiki Studio requires the complete DocTology source layout; an installed skill alone is not an application installation.
- Application code is not copied into connected vaults. Existing user `raw/`, `wiki/`, and `state/` locations are unchanged.

The [maintenance map](../dashboard/README.md#유지보수와-확장-경계) identifies module-level extension points. The old skill-internal dashboard paths are removed rather than kept as duplicate implementations.
