---
name: karpathy
description: >
  Use when the user wants a fully-autonomous iterate-and-score training loop that hacks code, runs it,
  and keeps changes that improve a single user-defined scalar metric — modelled on Karpathy's
  autoresearch program. One agent proposes one focused change at a time, runs training via the user's
  own run command, keeps the change only if the metric improves, else reverts; it tracks iterations as
  git branches or sandbox snapshots, gates each run on time or epochs, and loops forever until the
  human interrupts. Not for the analysis-first variant that profiles and reasons before editing (that
  is ml-autoresearch), and not for a budgeted, plateau-stopping refactor.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Karpathy Autoresearch Loop

A base single-agent **change → score → keep-or-revert** loop over training code. The artifact is the
set of `<editable_files>`; the feedback signal is a single scalar `<metric>` parsed from the training
run. You propose a change, run it, keep it only if the metric improved, revert otherwise, and repeat —
**forever, until the human interrupts.** You are the autonomous researcher: once the loop is running,
do not pause to ask permission.

Training runs in the **user's own environment** via the bound `<run_cmd>`; this skill ships no
dependencies and imports nothing — it edits code, shells out, and reads the metric back from the log.

## When to use

Use this for hands-off, leave-it-running optimization of a training script against one scalar metric,
where any improvement is kept blindly and the loop never self-terminates. Default to broad
freedom inside `<editable_files>` (architecture, optimizer, hyperparameters, model size); the only
hard limit is that the run finishes within the gate without crashing. Not for the analysis-first
variant that reasons about the data before editing (that is `ml-autoresearch`).

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` | scalar to minimize (lower is better); must appear in the training output | — | grep `<editable_files>`/README for `val_loss`, `val_acc`, `bpb`, `error`… |
| `<run_cmd>` | full shell command that launches one training run in the user's env | — | `pyproject.toml`/`.venv`/`uv.lock`/README run instructions |
| `<entrypoint>` | command that runs a single experiment | `<run_cmd>` | usually identical to `<run_cmd>` |
| `<editable_files>` | the file(s) the loop may modify; everything else is read-only | — | model/config/training source; exclude data, logs, eval harness |
| `<sandbox_root>` | where `results.tsv` + per-iteration snapshots live | `./sandbox` | — |
| `<iter_strategy>` | `branches` (git branch per run) or `snapshots` (folder per run) | `snapshots` | `snapshots` is safer off a clean tree; `branches` mirrors the original |
| `<gate>` | `time` (wall-clock) or `epochs` (fixed count) per run | — | existing time/epoch setting in the script or config |
| `<budget_minutes>` / `<budget_epochs>` | the gate's value | — | the inferred gate setting |

After confirmation, write `<sandbox_root>/results.tsv` with just the header (tab-separated, never
commas — they break in the description column). Use `iter` as the first column in snapshots mode,
`commit` in branches mode:
```
iter	<metric>	status	description
```
Also drop a copy of the resolved `loop.run.yaml` into each `iter<N>/` so every iteration is
auditable. In branches mode, create the run branch once (`autoresearch/<run_tag>`, must not already
exist). Leave `results.tsv` untracked — do not commit it.

## The loop

Training output is captured per iteration in `<run_log>` (default
`<sandbox_root>/iter<N>/run.log`). Copy this checklist and tick items off each pass:

- [ ] Iteration 0 — baseline: run `<entrypoint>` **unmodified**, parse `<metric>`, record it as the current best.
- [ ] Note state: branches → `git log --oneline -5` + short hash; snapshots → next iter N, confirm `iter<N>/` is fresh.
- [ ] Snapshot first (snapshots mode): copy every `<editable_files>` into `<sandbox_root>/iter<N>/code_snapshot/`.
- [ ] Apply one focused experimental change to `<editable_files>` (one idea per iteration).
- [ ] Run gated, redirecting all output to `<run_log>` (never `tee`, never flood context).
- [ ] Parse `<metric>` from `<run_log>`; empty output → crash (read the tail, fix-or-skip).
- [ ] Keep if `<metric>` improved on the best, else revert; append a `results.tsv` row.
- [ ] Go to the next iteration — never stop on your own.

**File edit guard.** Before touching any file at any step, confirm it is in `<editable_files>` —
every other file is read-only ground truth (the eval harness and `<metric>` are the truth the loop is
scored against; editing them would corrupt the signal). No exceptions.

**Baseline.** The first run is always the unmodified script, to fix the current-best `<metric>`.

**Propose one change.** For each later iteration pick a single focused idea (what to try and why) and
edit only the relevant `<editable_files>`. Architecture, optimizer, hyperparameters, batch size, model
size are all fair game; the only requirement is that the run finishes within the gate without
crashing. VRAM/memory is a soft constraint — some growth is fine for a real `<metric>` gain, but it
should not blow up. **Simplicity tiebreaker:** all else equal, simpler wins. A 0.001 gain that adds 20
lines of hacky code is not worth it; the same gain from *deleting* code is a clear keep, and equal
results from simpler code is a keep.

**Track the iteration.**
- *snapshots mode* — before editing, create `<sandbox_root>/iter<N>/` and copy every
  `<editable_files>` into `iter<N>/code_snapshot/` (preserving relative paths), plus a copy of
  `loop.run.yaml`. The snapshot is the revert point.
- *branches mode* — after editing, `git commit -am "<short idea>"` on the run branch. The commit is
  the revert point; do not commit `results.tsv`.

**Run gated.** Redirect stdout+stderr to `<run_log>`:
```bash
# time gate — wrap the entrypoint so it self-kills at the budget
timeout $(( <budget_minutes> * 60 )) <entrypoint> > <sandbox_root>/iter<N>/run.log 2>&1
# epoch gate — cap epochs by editing the controlling file in <editable_files>
<entrypoint> > <sandbox_root>/iter<N>/run.log 2>&1
```
A run should take about its budget plus a little eval overhead. If it has not terminated when it
should have, hard-kill it (time mode: at `2 × <budget_minutes>`) and treat it as a crash.

**Read the metric.**
```bash
grep '^<metric>:' <sandbox_root>/iter<N>/run.log
```
If that returns nothing, scan `tail -n 20 <run_log>` to find where the value is printed and lock in
that pattern for subsequent iterations.

**Handle a crash.** Empty metric ⇒ the run crashed. Read `tail -n 50 <run_log>` for the stack trace
and use judgement: a dumb, easy fix (typo, missing import) — fix it in `<editable_files>` and re-run
once (not more than a couple of times); a fundamentally broken idea — skip it, log `crash`, move on.

**Keep or revert.**
- **`<metric>` improved** (lower than the current best): status `keep`, update the best. Branches mode
  stays on the new commit (the branch advances); snapshots mode leaves the working files as they are.
- **Equal, worse, or crash:** status `discard` (or `crash`). Branches mode `git reset --hard HEAD~1`;
  snapshots mode restores every `<editable_files>` from `iter<N>/code_snapshot/`. If genuinely stuck
  you may rewind further, but do so very sparingly.

**Never stop on your own.** Once the loop has begun, do not ask "should I keep going?" — the human may
be away and expects you to run indefinitely until they interrupt. Out of ideas? Think harder: re-read
the in-scope files for new angles, combine near-misses from `results.tsv`, or try more radical
changes. (At `<budget_minutes>` minutes a run, that is roughly `60/<budget_minutes>` experiments an
hour — about 100 over a night, so the user wakes to a full `results.tsv`.)

## results.tsv (ledger)

`<sandbox_root>/results.tsv`, tab-separated, never commas in free text. First column is `iter`
(snapshots) or `commit` (branches); `status` ∈ {`keep`, `discard`, `crash`}; use `0.000000` for the
metric on a crash. Report the **best** iteration when interrupted, not necessarily the last.

```
iter	val_loss	status	description
1	0.997900	keep	baseline
2	0.993200	keep	increase LR to 0.04
3	1.005000	discard	switch to GeLU activation
4	0.000000	crash	double model width (OOM)
```
Branches mode is identical but keyed by short commit hash (e.g. `a1b2c3d`) instead of `iter`.

## Constraints

- **Only edit files in `<editable_files>`.** Confirm membership before touching any file — every other
  file, especially the eval harness that produces `<metric>`, is read-only ground truth.
- **One change per iteration**, so each `<metric>` delta is attributable to a single idea.
- **Run in the user's env via `<run_cmd>`/`<entrypoint>`.** This skill installs nothing and imports no
  training libraries — it shells out and reads the log. Do not add packages the project lacks.
- **Always redirect output to `<run_log>`**; never `tee`, never let training output flood your context.
- **`<sandbox_root>/` is self-contained** — no `../` path escapes, so an iteration stays auditable on
  its own.
- **Do not commit `results.tsv`** — leave it untracked.
- **Do not pause the loop to ask for direction**; it runs until the human interrupts.

## Stops

There is no automatic stop — this loop is unbounded by design and ends only when the human interrupts
it. A run is force-killed when it overruns its gate (treated as a crash, not a loop stop).
