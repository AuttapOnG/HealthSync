# HS-012 Per-feature harness memory refactor

Status: done · Branch: docs/harness-advancement

## Decisions

- Split `harness/progress.md` into bounded per-feature note files
  (`harness/notes/HS-XXX-*.md`) plus a slim index, because the append-only
  log had grown unbounded and was loaded into context on every harness read.
- Keep a "Cross-cutting decisions & events" section in `harness/progress.md`
  for decisions that span multiple features (timezone normalization,
  circuit-breaker suspension policy, secret/credential policy, deployments)
  so they are not hidden inside a single feature note or duplicated across
  several.

## Completed

- Migrated all decisions/events from the old dated `harness/progress.md`
  sections (2026-06-27, 2026-06-28, 2026-07-01, 2026-07-03) into per-feature
  notes under `harness/notes/` or the new cross-cutting log, with nothing
  dropped and nothing duplicated.
- Slimmed `harness/progress.md` to exactly three sections: Current State,
  Feature index, Cross-cutting decisions & events.
- Documented the new memory discipline in `harness/README.md` and mirrored
  it into the `AGENTS.md` Definition of Done.
- Added this feature entry to `harness/feature_list.json`.

## Remaining risk / dead-ends

- None known yet; future tasks in this batch (verification gate, `init.sh`)
  will exercise whether the new per-feature note discipline holds up in
  practice.
