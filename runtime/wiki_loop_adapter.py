"""DocTology's one-way binding to the bundled, independently usable loop skill.

Gate implementations stay in the skill. This adapter resolves their location;
it neither copies gates nor defines a second completion authority.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "llm-wiki-loop"
ENTRYPOINT = SKILL_ROOT / "scripts" / "wiki_loop.py"
CONTRACT = SKILL_ROOT / "SKILL.md"

if not ENTRYPOINT.is_file() or not CONTRACT.is_file():
    raise RuntimeError("The bundled llm-wiki-loop skill is missing. Keep the complete DocTology repository together.")

_spec = importlib.util.spec_from_file_location("doctology_loop_backend", ENTRYPOINT)
loop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loop)
workflow = loop.workflow
batch = loop.load_sibling("wiki_batch")
