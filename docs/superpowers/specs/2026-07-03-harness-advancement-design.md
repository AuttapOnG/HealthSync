# HealthSync Harness Advancement — Design

Date: 2026-07-03
Status: Approved (pending spec review)

## Goal

Advance the HealthSync harness toward the "mature" end of the harness-engineering
maturity model (per `awesome-harness-engineering`), scoped proportionately to a
small single-developer project. This spec covers the first batch of three
workstreams, in order:

1. **Memory refactor** — bounded, per-feature harness memory.
2. **Verification gate** — move verification from final review to in-loop.
3. **Reproducible env** — an `init.sh` bootstrap script.

Deferred (explicitly out of scope for now): OpenTelemetry traces, session replay,
agent-trajectory evals/benchmarks, multi-agent orchestration, and `.claude/`
slash commands / permissions tooling. These are tracked as a later batch.

## Current maturity baseline

| Axis | State before this work |
|------|------------------------|
| Instructions | Mature — `CLAUDE.md` + `AGENTS.md` + enforced read-order |
| Safety | Mature — dry-run default, double opt-in for real upload, circuit breaker, credential hygiene |
| Runtime state | Mature — `sync_state.json` with GCS generation guard |
| Memory | Emerging — single `harness/progress.md`, append-only, unbounded |
| Verification | Emerging — 89 tests but no automated in-loop gate; no lint/format/typecheck/CI |
| Reproducible env | Missing — no `init.sh` |

---

## Workstream 1 — Per-feature harness memory

### Problem

`harness/progress.md` is append-only and unbounded (currently 320 lines / ~18 KB,
one dated section per work day). The whole file is loaded into context every time
an agent reads the harness, so its context cost grows without limit.

### Design

Split harness memory into per-feature note files plus a slim, bounded index.

```
harness/
├── progress.md          # slim: Current State + Feature index + Cross-cutting log
└── notes/
    ├── HS-001-harness-and-prd.md
    ├── HS-002-weight-model.md
    ├── HS-003-adapter-interfaces.md
    ├── HS-004-zepp-life-source.md
    ├── HS-005-sync-state.md
    ├── HS-006-dry-run-destination.md
    ├── HS-007-garmin-destination.md
    ├── HS-008-zepp-life-poc.md
    ├── HS-009-cloud-function-entrypoint.md
    ├── HS-010-garmin-poc.md
    └── HS-011-harden-garmin-auth.md
```

**Per-feature note file** (`harness/notes/HS-XXX-<slug>.md`):

```markdown
# HS-XXX <title>

Status: <done|in-progress|...> · Branch: <branch or ->

## Decisions
## Completed
## Remaining risk / dead-ends
```

An agent working on a feature loads only that one file.

**Slim `harness/progress.md`** keeps only what is not owned by a single feature:

1. **Current State** — one paragraph: what is deployed, current branch, next work.
2. **Feature index** — table mapping each `HS-XXX` → its note file → status
   (a human-readable mirror of `feature_list.json` with links).
3. **Cross-cutting decisions & events** — chronological log of things that span
   multiple features: deployments, the timezone-normalization policy
   (models + garmin + zepp), the circuit-breaker suspension policy, and the
   secret/credential policy.

Rationale for keeping the cross-cutting log: decisions like timezone normalization
and destination suspension span several features. Filing them under one feature
note would hide them from the others or duplicate them. This section preserves the
chronological decision narrative that a pure per-feature split would lose. It grows
slowly because most day-to-day detail now lives in the feature notes.

### Migration

Redistribute the existing `harness/progress.md` content (four dated sections)
into the correct feature notes plus the cross-cutting log. No information is
dropped; content is moved, not deleted. Verbatim historical detail belongs in the
feature notes; only cross-feature items move to the new cross-cutting log.

### Discipline (who/when)

Add a rule to `harness/README.md` and to the Definition of Done in `AGENTS.md`:

- Record feature work in that feature's `harness/notes/HS-XXX-*.md`.
- Put only cross-feature decisions, deployments, and project-wide policy in
  `harness/progress.md`.
- Update the Current State paragraph and Feature index when a feature's status
  changes.

`CLAUDE.md`'s read-order is unchanged and still correct: read `harness/progress.md`
(now the index) first, then open the relevant feature note.

### Acceptance criteria

- `harness/notes/` contains one note file per feature in `feature_list.json`.
- `harness/progress.md` contains exactly the three sections above and no
  per-feature day-by-day detail.
- Every decision/event from the old `progress.md` is present either in a feature
  note or in the cross-cutting log (no information lost).
- `harness/README.md` and `AGENTS.md` document the new update discipline.

---

## Workstream 2 — In-loop verification gate

### Problem

The project has 89 passing tests but no automated gate: no linter, no formatter,
no type-checker, no CI. Verification is a final manual step. `AGENTS.md` already
leaves a TODO to add a formatter/linter and document its commands.

### Design

Add three layers, from fastest to most complete:

1. **Tooling config** in `pyproject.toml` (new file):
   - `ruff` for lint + format (line length and rule set chosen to match the
     existing code style; the current code is already clean and typed).
   - `mypy` for type-checking (the codebase already uses full type hints and
     `from __future__ import annotations`, so this is low-friction and high-value).
   - Pin these in `requirements-dev.txt`.

2. **CI** — a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on
   push and pull request:
   - `ruff check` + `ruff format --check`
   - `mypy healthsync`
   - `python -m pytest`
   - `python -m compileall healthsync`

3. **Local in-loop check (optional layer)** — a `.claude/settings.json` hook that
   runs `python -m pytest -q` after edits to `healthsync/**` or `tests/**`, so a
   broken change is caught inside the working loop rather than at review time.
   (If this proves noisy it can be dropped without affecting layers 1–2.)

Update the "Suggested Commands" and "Definition of Done" sections of `AGENTS.md`
to reference the real commands, resolving the existing TODO.

### Acceptance criteria

- `ruff check`, `ruff format --check`, and `mypy healthsync` all pass on the
  current tree (fixing any issues they surface as part of this work).
- `.github/workflows/ci.yml` runs lint, format-check, type-check, tests, and
  compile on push and PR.
- `requirements-dev.txt` pins `ruff`, `mypy`, and `pytest`.
- `AGENTS.md` "Suggested Commands" lists the real gate commands; the linter TODO
  is removed.
- Existing 89 tests still pass.

---

## Workstream 3 — Reproducible env (`init.sh`)

### Problem

There is no single reproducible bootstrap. A new agent or developer must know to
install three separate requirements files in the right order.

### Design

Add an idempotent `init.sh` at the repo root that:

1. Creates a virtual environment (`.venv`) if absent.
2. Upgrades `pip`.
3. Installs `requirements.txt`, `requirements-dev.txt`, and `requirements-poc.txt`.
4. Prints next steps (copy `.env.example` → `.env`, run `python -m pytest`).

The script must be safe to re-run (idempotent) and must not touch or print
secrets. Document it in `README.md` and reference it from `harness/README.md` as
the environment-bootstrap step.

### Acceptance criteria

- `bash init.sh` on a clean checkout produces a working `.venv` with all
  dependencies and a green `python -m pytest`.
- Re-running `init.sh` is a no-op-safe (does not error, does not duplicate work
  destructively).
- `init.sh` never prints or commits secrets.
- `README.md` documents `init.sh` as the setup entrypoint.

---

## Sequencing

1. Workstream 1 (memory refactor) — establishes where all subsequent decisions
   get recorded.
2. Workstream 2 (verification gate) — highest ongoing value.
3. Workstream 3 (`init.sh`) — cheap, supports the CI/dev loop.

Each workstream is independently shippable and independently verifiable.

## Out of scope (later batch)

- `.claude/` permissions allowlist and harness slash commands
  (`/harness-status`, `/next-feature`).
- OpenTelemetry traces / structured run history / session replay.
- Agent-trajectory evaluations and benchmarks.
- Multi-agent orchestration.
