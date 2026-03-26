# Fixture: Repo Dependency Claims

This fixture models a small repo-like dependency note.
The accepted claim is that `svc.api` depends on `lib.search`.
The intended derived edge is the reverse support edge `lib.search supports svc.api`.

Use this fixture to verify:

- claims and evidence remain canonical
- derived edges are regenerated, not hand-curated truth
- only accepted claims materialize
