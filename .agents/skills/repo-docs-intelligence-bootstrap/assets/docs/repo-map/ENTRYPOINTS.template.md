---
status: Active
source_of_truth: No
last_updated: YYYY-MM-DD
superseded_by: N/A
---

# Entrypoints

## Canonical Entrypoints

List confirmed CLI, HTTP, package, script, or application entrypoints. Preserve the exact registered command name and `module:symbol` target for Python entrypoints so the validator can compare docs with live package metadata.

| Surface | Path Or Registration | Owner | Notes |
| --- | --- | --- | --- |
| Example CLI | `pyproject.toml` -> `package.cli:main` | package | Replace with live evidence. |

## Secondary Wrappers

List wrappers, aliases, or operator shortcuts that are still live but not canonical.

## Verification Notes

Record how each entrypoint was confirmed, such as package metadata, imports, route registration, or tests.
