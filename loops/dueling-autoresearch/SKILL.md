---
name: dueling-autoresearch
description: >
  Use when the user wants two approaches raced head-to-head on a single shared metric — e.g.
  a classical/algorithmic lane vs an ML/learned lane, or any two strategies for the same task.
  Each lane runs its own analysis-first research loop confined to its lane, the lanes share a
  scoreboard and may borrow ideas across the boundary without abandoning their identity, and a
  shared eval keeps the head-to-head honest; loops until interrupted, reporting the current
  leader. Not for improving a single approach in isolation (use a single-track research loop),
  and not for picking between two finished artifacts in one shot (that is a one-time comparison).
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Dueling Autoresearch Loop

Two lanes work the **same** objective in parallel and **race the same metric** — by default a
**classical/algorithmic** lane against an **ML/learned** lane (the lanes are user-named). Each lane
runs its own analysis-first iteration via `roles/TrackAgent.md`, **confined to its lane**. Every
round both lanes post to a shared `duel_log.md` scoreboard and may **borrow ideas** across the lane
boundary — but each stays in its lane. The feedback signal is the shared `<metric>` on a shared
eval: if the classical lane wins, that is a real result. Lanes support **mixed code locations** — a
`codebase` lane edits existing repo files, a `sandbox` lane authors its own code — and an
**eval-parity gate** keeps the scores comparable.

You are the orchestrator: each round you advance both lanes, update the scoreboard, and keep both
honest. Do not pause for permission once the loop is running.

## When to use

Use this to race two genuinely different approaches on one metric and keep them honest against the
same eval — classical vs learned, two model families, two query strategies. Default to spawning both
lanes in parallel and letting the scoreboard drive cross-lane idea borrowing; if a lane runs dry,
push it to a more radical in-lane change or to borrow a fresh idea from the log. Not for tuning a
single approach (use a single-track loop), and not for a one-shot comparison of two finished things.

The cast (all in this folder):
- `roles/TrackAgent.md` — the per-lane researcher, instantiated once per lane.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm the values before creating any other files.

The host also decides **spawn-or-degrade**: on Claude Code spawn a real `Agent` per lane so the two
run **in parallel**; otherwise adopt `roles/TrackAgent.md` inline and run the lanes sequentially.

**Shared bindings** (identical for both lanes — the honesty anchor):

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` | the single metric both lanes race; ground truth of the duel | — | ask; scan run logs for a printed score |
| `<metric_direction>` | `minimize` or `maximize` | — | from the metric's nature (loss vs accuracy) |
| `<gate>` | run budget unit: `time` or `epochs` | `epochs` | the artifact's runner |
| `<budget>` | epochs per run (or minutes if `gate: time`) | 5 | — |
| `<sandbox_root>` | where snapshots, ledgers, and the duel log live | `./sandbox` | — |
| `<iter_strategy>` | `snapshots` or `branches` (snapshots recommended — two lanes on one branch is simplest) | `snapshots` | — |

**Per-lane bindings** (two lanes, default names `classical` and `learned`). Each lane has a
`code_location` that decides which other fields it needs — **never add code to the codebase**:

| field | meaning | when |
|---|---|---|
| `name` | lane name | always |
| `code_location` | `codebase` or `sandbox` | always |
| `run_cmd` | existing entrypoint to run, e.g. `python train.py` | if `codebase` |
| `editable_files` | existing repo files this lane may edit | if `codebase` |
| `entry` | command run from inside `<sandbox_root>/<lane>/iter<N>/`, e.g. `python run.py` | if `sandbox` |

- **`codebase`** — the lane maps to existing code: edits its `editable_files` and runs `run_cmd`.
  Two `codebase` lanes must have **non-overlapping** `editable_files`.
- **`sandbox`** — no implementation exists and none is added to the repo: the lane **authors and runs
  its code inside `<sandbox_root>/<lane>/iter<N>/`** via `entry`.

> **Typical duel on a repo with one existing model:** the **learned** lane is `codebase` (edits
> `model.py`/`config.yaml`, runs `train.py`); the **classical** lane is `sandbox` (authors its own
> code under `<sandbox_root>/classical/iter<N>/`). Nothing is added to the codebase, yet the
> classical lane is still built and iterated.

**Eval-parity gate (the honesty anchor).** Before starting, confirm **both lanes report `<metric>`
on the same held-out set, computed the same way**, so the scores are comparable — state how each lane
emits it (e.g. both print `<metric>:` to their run log). If they don't match, fix it first; the duel
is meaningless otherwise. If `gate: time`, write a `run_with_timeout.sh` wrapper per lane
(`timeout $(( <budget> * 60 )) <entry-or-run_cmd> "$@"`).

**Initialise the sandbox** (after confirmation):
```
<sandbox_root>/
├── duel_log.md          ← shared channel + scoreboard (## Scoreboard, ## Round log; headers only)
├── <laneA>/results.tsv  ← lane A ledger, header only
└── <laneB>/results.tsv  ← lane B ledger, header only
```
Each lane's per-iteration work lives in `<sandbox_root>/<lane>/iter<N>/` (`analysis/`, `results/`,
the run log). A `codebase` lane's iter dir also holds `code_snapshot/` (the pre-change copy for
revert); a `sandbox` lane's iter dir holds the lane's **actual code** for that iteration (a kept
iteration carries forward as the next one's starting point).

## The loop (duel)

Each **round** advances **both** lanes by one iteration. On Claude Code, spawn the two TrackAgents in
**parallel** (one turn, two `Agent` calls); otherwise run lane A then lane B inline. A track is one
analysis-first iteration confined to its lane — the 8 steps in `roles/TrackAgent.md`. **Round 1** is
each lane's baseline (a `codebase` lane runs unmodified; a `sandbox` lane authors its initial
implementation in `iter1/`). **One change per lane per round**, so each metric delta is attributable.

Copy this checklist and tick items off each round:
- [ ] **State** — note round N; read `duel_log.md` (both lanes' latest posts + the scoreboard).
- [ ] **Advance each lane** — run a TrackAgent (`roles/TrackAgent.md`) per lane, given its lane
      bindings, the shared `<metric>`/`<metric_direction>`/`<gate>`/`<budget>`, and `duel_log.md`.
- [ ] **Track posts** — each lane appends its round entry to `duel_log.md` (best `<metric>`, one key
      finding, any dead end, one idea the other lane could borrow).
- [ ] **Scoreboard** — update `## Scoreboard`: best `<metric>` per lane and the current leader (per
      `<metric_direction>`); optionally flag one cross-pollination suggestion for next round.
- [ ] **Continue** — go to the next round; never pause to ask whether to continue.

**Spawn-or-degrade per lane.** Where the host supports it, spawn a real isolated TrackAgent per lane
(Claude Code: an `Agent` per lane, both launched in one turn for parallelism). Otherwise adopt
`roles/TrackAgent.md` inline and run the lanes sequentially. Each TrackAgent is confined to its lane
and returns its iteration summary to the orchestrator.

## Ledger

Two ledgers: a **per-lane `results.tsv`** for each lane's experiments, and the **shared
`duel_log.md`** scoreboard + round posts.

**Per-lane `<sandbox_root>/<lane>/results.tsv`** (tab-separated, never commas in free text):
```
iter	<metric>	status	analysis_summary	description
1	0.6320	keep	baseline; classical features, logistic head	baseline
2	0.6610	keep	added HOG features; per-class gains on textured classes	add HOG feature extractor
```
`status` ∈ {`keep`, `discard`, `crash`} (`0.000000` for `<metric>` on crash).

**Shared `<sandbox_root>/duel_log.md`** — scoreboard + per-round posts:
```
## Scoreboard
round	classical_best	learned_best	leader
1	0.6320	0.6480	learned
2	0.6610	0.7050	learned

## Round log
### Round 2
- **classical** — best 0.6610 (this iter 0.6610). Finding: HOG helps textured classes
  (results/per_class.txt). Dead end: raw-pixel kNN plateaus. Borrow: learned's augmentation
  could expand classical's training set.
- **learned** — best 0.7050. Finding: BN fixed conv2 saturation. Dead end: dropout hurt at this
  budget. Borrow: classical's HOG features as an aux input channel.
```
Report the **current leader** (per `<metric_direction>`), never a final winner — a lane that is
behind can still come back. Leave `results.tsv`, `duel_log.md`, and `iter*/` untracked (do not
commit them).

## Constraints
- **Never add code to the codebase.** A `codebase` lane edits only its own `<editable_files>`; a
  `sandbox` lane lives entirely in `<sandbox_root>/<lane>/`. Lanes never touch each other's files —
  every other file is the evaluation ground truth.
- **Stay in lane.** A lane borrows *ideas*, never converts into the other approach — a classical lane
  stays classical even if it borrows a loss/target idea from the learned lane.
- **Same metric, same eval.** Both lanes optimize `<metric>` on the same held-out set computed the
  same way; never compare otherwise. Do not modify the evaluation/metric — it is the shared ground
  truth that makes the duel honest.
- **One change per lane per round**, so each metric delta is attributable.
- Do not install new packages or add dependencies the project lacks; helper code stays stdlib-only.
- Redirect each run's output to its lane's run log; never use `tee`. The sandbox is self-contained —
  no `../` escapes.
- Do not pause the loop to ask for direction; once running, keep both lanes iterating until manually
  interrupted, and report the current leader rather than declaring a final winner.
