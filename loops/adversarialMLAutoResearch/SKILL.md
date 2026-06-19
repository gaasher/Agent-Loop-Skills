---
name: adversarialMLAutoResearch
description: >
  Use when the user wants an autonomous ML research loop where competing ideas are
  pressure-tested before compute is spent. Each iteration, n research subagents each
  propose one architecture change; a Judge critiques them against a rubric, the agents
  refine, and the Judge ranks and picks the single change to run. The Judge learns to
  pick better over time by scoring its predictions against realized outcomes. Otherwise
  behaves like standardMLAutoresearch (analysis-first). Loops forever until interrupted.
metadata:
  version: "0.1.0"
---

# Adversarial ML Autoresearch Loop

Same analysis-first experiment mechanics as `standardMLAutoresearch`, but the single
"form a hypothesis" step is replaced by an **idea tournament**: `<n>` agents propose
competing changes, a **Judge** critiques and ranks them, the agents refine once, and the
Judge picks **one** change to run. The Judge is the orchestrator and **self-calibrates** —
it learns which ideas pay off by comparing its predictions to realized results.

**You are the Judge.** Adopt `roles/Judge.md`; spawn the proposers with
`roles/ResearchAgent.md`. Do not pause for permission once the loop is running.

The cast and files (all in this folder):
- `roles/Judge.md` — your detailed behavior (critique, rank, decide, self-calibrate).
- `roles/ResearchAgent.md` — the proposer role, spawned `<n>` times each round.
- `rubric.md` — the scoring criteria (shipped defaults; copied to a working copy at setup).
- `schemas/idea.schema.json` — what an agent returns (one proposed change).
- `schemas/verdict.schema.json` — what the Judge records for one idea (scores, rank, decision).

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. You MUST ask every question below and wait for the user's
explicit answer. Do NOT infer, skip, or auto-apply any answer. If you skip any, you are
doing it wrong.**

### 1.0 Detect host
Check whether `AskUserQuestion` is available.
- **Yes → Claude Code path**: scan the project to infer each answer, present it as the
  recommended option via `AskUserQuestion`.
- **No → plain-text path**: ask each question as a quoted prompt and wait for a reply.

Record **`<host>`** = `claude-code` or `other`. (Host also decides spawn-or-degrade: on
Claude Code spawn real `Agent` subagents for the proposers; otherwise adopt the
ResearchAgent role inline, one proposal at a time.)

### 1a. Metric
Record **`<metric>`** and **`<metric_direction>`** (`minimize`/`maximize`). Claude Code:
infer from code/README and recommend; Other: *"What scalar metric should I optimize, and
minimize or maximize?"*

### 1b. Environment & run command
Record **`<run_cmd>`** / **`<entrypoint>`**. Claude Code: infer from `pyproject.toml`/venv/
README. Other: *"What command runs one training experiment end to end?"*

### 1c. Editable files
Record **`<editable_files>`** (model/config/training script — never the eval harness).
**FILE EDIT GUARD**: before touching any file at any point, confirm it's in
`<editable_files>`. Everything else is read-only.

### 1d. Sandbox location
Record **`<sandbox_root>`** (default `./sandbox/`).

### 1e. Iteration strategy
Record **`<iter_strategy>`** = `branches` or `snapshots`. If `branches`: create
`git checkout -b autoresearch/<tag>` (today's date; must not exist).

### 1f. Gate
Record **`<gate>`** = `time` or `epochs` and **`<budget>`**. If `time`, write
`<sandbox_root>/run_with_timeout.sh` (`timeout $(( <budget> * 60 )) <entrypoint> "$@"`);
hard-kill at `2 × <budget>` min. If `epochs`, cap the epoch count in an editable file.

### 1g. Number of proposing agents
Record **`<n>`** (default 3). Claude Code: recommend `3 — enough competition without
spawning a crowd`; Other: *"How many agents should propose competing ideas each round?
(Suggested: 3)"*

### 1h. Refinement rounds
Record **`<refine_rounds>`** (default 1). Other: *"How many propose→critique→refine rounds
per iteration before the Judge decides? (Suggested: 1)"*

### 1i. Initialise sandbox
```
<sandbox_root>/
├── schema.yaml          ← resolved bindings (written now)
├── results.tsv          ← experiment ledger, header only (written now)
├── rubric.active.md     ← copy of rubric.md (the Judge self-refines THIS, not the skill's)
├── calibration.tsv      ← judge predicted-vs-realized ledger, header only
├── judge_lessons.md     ← append-only judge lessons (header only)
└── iter1/               ← created at loop start
```
**`results.tsv` header** (tab-separated, no commas): `iter	<metric>	status	analysis_summary	description`
**`calibration.tsv` header**: `iter	idea_id	grounding	impact	feasibility	pred_direction	pred_magnitude	confidence	realized_delta	hit`
Copy `rubric.md` → `<sandbox_root>/rubric.active.md`. Write all bindings (incl. `n`,
`refine_rounds`) to `schema.yaml`.

### 1j. Confirm and go
Print every resolved binding. **Do not create files or start until the user confirms.**

---

## 2. The loop

`<run_log>` = the file capturing training output for an iteration (default
`<sandbox_root>/iter<N>/<run_log>`). Everything in `<editable_files>` is fair game; code
must run and finish within `<budget>`. **Simplicity criterion** (as in `standard`): equal
metric but simpler code is a `keep`. **One change per iteration** — the tournament yields
exactly one. **First run**: iteration 1 is the unmodified baseline (skip the tournament;
just run + analyse to seed the first analysis summary).

### LOOP FOREVER:

1. **State.** *branches*: `git log --oneline -5`. *snapshots*: confirm `iter<N>/` is new.
2. **Tournament (iter 2+)** — run it as the Judge (`roles/Judge.md`):
   propose (spawn `<n>` ResearchAgents) → critique & score against `rubric.active.md`
   (gate → pointwise learning signal → **de-biased pairwise to rank**) → refine
   `<refine_rounds>`× → **select the single top-ranked change** (no merge). Write ideas to
   `iter<N>/ideas/` and one verdict per idea to `iter<N>/verdicts/`; log the Judge's predicted
   outcome for the winner to `calibration.tsv`.
3. **Snapshot / commit, then apply the winning change.** *snapshots*: copy `<editable_files>`
   → `iter<N>/code_snapshot/`, copy `schema.yaml` → `iter<N>/`, apply the change. *branches*:
   apply, `git commit -am "<idea_id>: <short description>"`.
4. **Analysis plan** → `iter<N>/analysis/plan.md` (standard format): deliverables table
   including the winner's `prediction` **and** any useful analysis steps from the
   *losing* ideas. ≥1 row must cover a not-yet-measured dimension.
5. **Run** (redirect, never `tee`) → **read metric** (`grep '^<metric>:' <run_log>`; on empty,
   `tail -n 50`, one trivial fix, else `crash`).
6. **Analyse — mandatory, real artifacts.** Execute every `plan.md` row → files in
   `iter<N>/results/`; verify none missing; interpret; check the winner's `prediction`;
   write a 3–8 bullet analysis summary ending in the empirical anchor for the next round.
   (Same discipline as `standardMLAutoresearch` step 6.)
7. **Log.** Append the `results.tsv` row (`iter|<metric>|status|analysis_summary|description`;
   `0.000000` on crash). Append the realized delta + `hit` to `calibration.tsv` against the
   prediction.
8. **Keep or revert.** Improved → `keep`, update best. Equal/worse/crash → `discard`/`crash`
   (*branches* `git reset --hard HEAD~1`; *snapshots* restore from `code_snapshot/`). Apply
   the simplicity criterion before logging `discard`.
9. **Self-calibrate** (`roles/Judge.md`): update `judge_lessons.md`, refine `rubric.active.md`
   (weights + anchors, bounded, from realized outcomes), update the selection hit-rate.
10. **Go to step 1.**

---

**NEVER STOP**: once running, do not pause to ask "should I continue?". The human expects you
to work indefinitely until manually stopped. If ideas run dry: tell the agents to pivot harder,
push proposal diversity, mine `results.tsv`/`calibration.tsv` for under-explored directions,
go deeper on analysis. The loop runs until interrupted.

---

## 3. Ledger formats

**`results.tsv`** (tab-separated, never commas) — same as `standardMLAutoresearch`:
```
iter	<metric>	status	analysis_summary	description
1	0.6320	keep	baseline; grad norms even, no pathologies	baseline
2	0.6890	keep	layer-2 activations near-saturated; BN helped	iter2-a1: add BatchNorm after conv2
```

**`calibration.tsv`** (tab-separated) — the Judge's track record:
```
iter	idea_id	grounding	impact	feasibility	pred_direction	pred_magnitude	confidence	realized_delta	hit
2	iter2-a1	5	4	4	improve	+2%	high	+0.057	1
```

Do not commit `results.tsv`, `calibration.tsv`, `judge_lessons.md`, `rubric.active.md`, or
`iter*/` to git. Leave them untracked.

---

## 4. Hard constraints (never violate)
- **Only edit files in `<editable_files>`.** Confirm before every edit.
- Do not install new packages or add dependencies not already present.
- Do not modify the evaluation harness — `<metric>` is the ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect training output to `<run_log>`. Never use `tee`.
- The sandbox must be self-contained — no `../` escapes.
- **Exactly one change per iteration** (the tournament winner). No merging ideas.
- The Judge edits only `rubric.active.md` (the working copy), never the shipped `rubric.md`.
- An idea with no testable `prediction` is rejected before scoring; the rank is decided
  by de-biased pairwise comparison, never by the pointwise scores.
