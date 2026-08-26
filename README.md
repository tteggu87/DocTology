<p align="center">
  <img src="branding/doctology-logo-cropped.jpeg" alt="DocTology logo" width="820" />
</p>

# DocTology

DocTology is a small distribution repository for three agent skills:

| Skill | Purpose |
| --- | --- |
| `llm-wiki-bootstrap` | Create an Obsidian-first Markdown wiki, with optional disposable SQLite retrieval. |
| `llm-wiki-loop` | Grow and certify an existing wiki through semantic and procedural gates. |
| `repo-docs-intelligence-bootstrap` | Keep repository docs, contracts, and durable working memory aligned with code. |

There is no active ontology profile, canonical JSONL warehouse, GUI workbench, or repository-owned corpus. Earlier experiments remain available through Git history and archive tags.

## Install or synchronize

```bash
python3 scripts/manage_skills.py check
python3 scripts/manage_skills.py install
```

`install` copies the exact three source directories into `~/.codex/skills`. Use `--target PATH` for another skill root and `--dry-run` to preview changes.

## Verify

```bash
python3 -m unittest discover -s tests
git -c core.quotepath=false diff-tree --root --no-commit-id --name-only -r HEAD > /tmp/doctology-changed-files.txt
python3 .agents/skills/repo-docs-intelligence-bootstrap/scripts/validate_repo_docs_intelligence.py --repo-root . --changed-files /tmp/doctology-changed-files.txt
```

The command validates the paths changed by the current commit. During uncommitted development, pass a normalized list matching the working-tree changes instead.

See [the documentation portal](docs/README.md) for architecture and maintenance details.
