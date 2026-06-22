---
name: tournament-autoresearch
description: >
  Use when the user wants an autonomous ML research loop that pressure-tests competing ideas before
  spending compute — several research subagents each propose one architecture change, a self-calibrating
  Judge critiques them against a rubric, the proposers refine, and the Judge picks the single change to
  run. The Judge learns to pick better over time by scoring its own predictions against realized
  metric deltas, recording predicted-vs-realized in a calibration ledger and refining its working
  rubric. The result is an experiment ledger where each iteration's change won a de-biased tournament.
  Not for running a single pre-decided experiment, and not for analysis-only exploration — for one
  hypothesis proposed and run per iteration without competition, use the sibling ml-autoresearch loop.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Tournament Autoresearch Loop

An ML autoresearch loop whose single "form a hypothesis" step is replaced by an **idea tournament**.
The artifact is an experiment ledger; the feedback signal is the **realized `<metric>` delta** of the
change that won the tournament. Each iteration `<n>` ResearchAgents propose competing architecture
changes, a **Judge** critiques and ranks them, the proposers refine, and the Judge selects **one**
change to run. The Judge is the orchestrator and **self-calibrates**: it scores its predictions
against realized results, so it learns which kinds of ideas actually pay off. The experiment mechanics
(snapshot → run → mandatory analysis → keep/revert) match the sibling `ml-autoresearch` loop.

## When to use

Use this for open-ended ML experimentation where competing ideas should be vetted before compute is
spent and the picker should improve over time. **You are the Judge**: adopt `roles/Judge.md` and spawn
the proposers with `roles/ResearchAgent.md`. Default to `<n>` competing proposers with one refine
round; widen `<n>` or add rounds when ideas are converging too fast. Not for running a single
pre-decided experiment, and not for analysis-only exploration over a dataset — for one uncompeted
hypothesis per iteration use the sibling `ml-autoresearch` loop.

The cast and files (all in this folder):
- `roles/Judge.md` — your behavior: critique, rank, decide, self-calibrate.
- `roles/ResearchAgent.md` — the proposer role, spawned `<n>` times each round.
- `rubrics/rubric.md` — the scoring criteria (shipped defaults; copied to a working copy at setup).
- `schemas/idea.schema.json` — what a proposer returns (one proposed change).
- `schemas/verdict.schema.json` — what the Judge records per idea (scores, rank, decision).

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

Record `<host>` (`claude-code` or `other`) once — it also decides spawn-or-degrade: on Claude Code
spawn real `Agent` subagents for the proposers, all in one turn; otherwise adopt the ResearchAgent
role inline, one proposal at a time.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` | scalar metric to optimize | — | infer from code/README; ask direction |
| `<metric_direction>` | `minimize` or `maximize` | — | infer from the metric's meaning |
| `<run_cmd>` / `<entrypoint>` | command that runs one experiment end to end | — | `pyproject.toml`/`.venv`/README |
| `<editable_files>` | model/config/training files the loop may edit; never the eval harness | — | scan for the model + training script |
| `<sandbox_root>` | where snapshots + ledgers live | `./sandbox` | — |
| `<iter_strategy>` | `branches` or `snapshots` | `snapshots` | git present → offer `branches` |
| `<gate>` / `<budget>` | `time` (minutes) or `epochs`, plus the cap | `epochs` / — | infer epoch arg from the script |
| `<n>` | proposers competing each round | 3 | recommend 3 — competition without a crowd |
| `<refine_rounds>` | propose→critique→refine rounds before the Judge decides | 1 | — |

If `<iter_strategy>` is `branches`, create `git checkout -b autoresearch/<run_tag>` (must not exist).
If `<gate>` is `time`, write `<sandbox_root>/run_with_timeout.sh`
(`timeout $(( <budget> * 60 )) <entrypoint> "$@"`) and hard-kill at `2 × <budget>` min; if `epochs`,
cap the epoch count in an editable file.

**Initialize the sandbox** (after confirmation):
```
<sandbox_root>/
├── loop.run.yaml       ← resolved bindings (written now)
├── results.tsv         ← experiment ledger, header only
├── calibration.tsv     ← Judge predicted-vs-realized ledger, header only
├── judge_lessons.md    ← append-only Judge lessons (header only)
├── rubric.active.md    ← copy of rubrics/rubric.md; the Judge self-refines THIS, never the shipped one
└── iter1/              ← created at loop start
```
Copy `rubrics/rubric.md` → `<sandbox_root>/rubric.active.md`. Write the headers (see [Ledger](#ledger)).

## The loop

`<run_log>` = the file capturing training output for an iteration (default
`<sandbox_root>/iter<N>/run.log`). Everything in `<editable_files>` is fair game; code must run and
finish within `<budget>`. **Simplicity criterion**: equal metric but simpler code is a `keep`. The
tournament yields **exactly one** change per iteration. **Iteration 1** is the unmodified baseline —
skip the tournament; just run + analyse to seed the first analysis summary.

Copy this checklist and tick items off, looping until interrupted:
- [ ] **State.** *branches*: `git log --oneline -5`. *snapshots*: confirm `iter<N>/` is new.
- [ ] **Tournament (iter 2+)** — run it as the Judge (`roles/Judge.md`): propose (spawn `<n>` ResearchAgents) → critique & score against `rubric.active.md` → refine `<refine_rounds>`× → select the single top-ranked change.
- [ ] **Snapshot/commit, then apply** the winning change.
- [ ] **Analysis plan** → `iter<N>/analysis/plan.md`: deliverables table covering the winner's `prediction` plus useful steps from losing ideas; ≥1 row on a not-yet-measured dimension.
- [ ] **Run** (redirect, never `tee`) → read metric.
- [ ] **Analyse** — execute every `plan.md` row → `iter<N>/results/`; check the winner's `prediction`; write a 3–8 bullet summary ending in the empirical anchor for next round.
- [ ] **Log** the `results.tsv` row and the realized delta + `hit` to `calibration.tsv`.
- [ ] **Keep or revert** (simplicity criterion before logging `discard`).
- [ ] **Self-calibrate** (`roles/Judge.md`): update `judge_lessons.md`, refine `rubric.active.md`, update the hit-rate.

In detail, each iteration:

1. **State.** *branches*: `git log --oneline -5`. *snapshots*: confirm `iter<N>/` is new.
2. **Tournament (iter 2+).** As the Judge (`roles/Judge.md`): spawn `<n>` ResearchAgents
   (spawn-or-degrade by `<host>`) with `roles/ResearchAgent.md`, the latest analysis summary, and
   `schemas/idea.schema.json`. Critique & score each against `rubric.active.md` — gate (reject ideas
   with no testable `prediction`, unscored) → pointwise 0–5 per axis as the learning signal →
   **de-biased pairwise to rank** (compare each pair in *both* orders, keep only consistent verdicts).
   Refine `<refine_rounds>`×, re-score, then **select the single `rank == 1` change** (no merging).
   Write ideas to `iter<N>/ideas/`, one verdict per idea to `iter<N>/verdicts/`, and log the Judge's
   predicted outcome for the winner to `calibration.tsv`.
3. **Snapshot/commit, then apply the winning change.** *snapshots*: copy `<editable_files>` →
   `iter<N>/code_snapshot/`, copy `loop.run.yaml` → `iter<N>/`, apply the change. *branches*: apply,
   `git commit -am "<idea_id>: <short description>"`.
4. **Analysis plan** → `iter<N>/analysis/plan.md`: a deliverables table including the winner's
   `prediction` and any useful analysis steps from the *losing* ideas. ≥1 row must cover a
   not-yet-measured dimension.
5. **Run** (redirect to `<run_log>`, never `tee`) → read the metric (`grep '^<metric>:' <run_log>`;
   on empty, `tail -n 50`, one trivial fix, else log `crash`).
6. **Analyse — mandatory, real artifacts.** Execute every `plan.md` row → files in `iter<N>/results/`;
   verify none missing; interpret; check the winner's `prediction`; write a 3–8 bullet analysis
   summary ending in the empirical anchor for the next round.
7. **Log.** Append the `results.tsv` row (`0.000000` on crash). Append the realized delta + `hit` to
   `calibration.tsv` against the prediction.
8. **Keep or revert.** Improved → `keep`, update best. Equal/worse/crash → `discard`/`crash`
   (*branches* `git reset --hard HEAD~1`; *snapshots* restore from `code_snapshot/`). Apply the
   simplicity criterion before logging `discard`.
9. **Self-calibrate** (`roles/Judge.md`): update `judge_lessons.md`, refine `rubric.active.md`
   (weights + anchors, bounded, from realized outcomes), update the selection hit-rate.
10. **Go to step 1.**

**Never stop.** Once running, do not pause to ask "should I continue?" — the loop runs until manually
interrupted. If ideas run dry: push proposal diversity, mine `results.tsv`/`calibration.tsv` for
under-explored directions, go deeper on analysis.

## Ledger

Three append-only files under `<sandbox_root>`, all tab-separated, never commas in free text.

**`results.tsv`** — the experiment ledger (same format as `ml-autoresearch`). Header:
```
iter	<metric>	status	analysis_summary	description
```
`status` ∈ {`keep`, `discard`, `crash`}. Example:
```
iter	val_acc	status	analysis_summary	description
1	0.6320	keep	baseline; grad norms even, no pathologies	baseline
2	0.6890	keep	layer-2 activations near-saturated; BN helped	iter2-a1: add BatchNorm after conv2
```

**`calibration.tsv`** — the Judge's track record (predicted vs realized). Header:
```
iter	idea_id	grounding	impact	feasibility	pred_direction	pred_magnitude	confidence	realized_delta	hit
```
Example:
```
iter	idea_id	grounding	impact	feasibility	pred_direction	pred_magnitude	confidence	realized_delta	hit
2	iter2-a1	5	4	4	improve	+2%	high	+0.057	1
```

**`judge_lessons.md`** — append-only prose, 1–3 bullets per iteration: which axis tracked gains, what
kind of idea was over/under-rated, and the reason for each `rubric.active.md` refinement. Example:
```
## iter 2
- grounding tracked the gain (BN tied to the dead-unit finding hit +0.057, as predicted).
- bumped grounding weight 0.40 → 0.45; tightened the impact anchor (impact=5 picks over-promised).
```

Report the **best** iteration (highest `keep` metric), not necessarily the last, plus the running
selection hit-rate. Leave `results.tsv`, `calibration.tsv`, `judge_lessons.md`, `rubric.active.md`,
and `iter*/` untracked.

## Constraints
- **Only edit files in `<editable_files>`** — confirm before every edit, because everything else
  (especially the eval harness) is read-only ground truth defining `<metric>`.
- **Exactly one change per iteration** (the tournament winner) — no merging ideas — so each metric
  delta is attributable to one change.
- An idea with no testable `prediction` is **rejected before scoring**; the rank is decided by
  de-biased pairwise comparison, never by the pointwise scores (which only feed calibration).
- The Judge edits only `rubric.active.md` (the working copy), never the shipped `rubrics/rubric.md`.
- Always redirect training output to `<run_log>`; never `tee` (it floods your context).
- Do not install packages or add dependencies the project lacks; helper code stays stdlib-only.
- Do not modify the evaluation harness, and do not pause the loop to ask for direction.
- The sandbox must be self-contained — no `../` escapes.
