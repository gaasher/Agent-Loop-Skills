---
name: duelingMLAutoresearch
description: >
  Use when the user wants two approaches raced head-to-head on the same task — e.g.
  classical/algorithmic vs ML/learned. Two tracks each run an analysis-first research
  loop in their own lane, share findings each round through a common log, and may borrow
  ideas across the lane boundary (without abandoning their own identity). A shared metric
  and eval keep the duel honest. Loops forever until interrupted.
metadata:
  version: "0.1.0"
---

# Dueling ML Autoresearch Loop

Two tracks work the **same** objective in parallel — by default a **classical/algorithmic**
lane and an **ML/learned** lane (the lanes are user-named). Each track runs the
`standardMLAutoresearch` analysis-first loop in its own lane and sandbox. Every round they
**communicate** through a shared `duel_log.md` (findings, baselines, dead ends, borrowable
ideas) and may **borrow ideas** from each other — but each **stays in its lane**. A shared
metric and eval keep the head-to-head honest: if the classical lane wins, that's a real result.

**You are the orchestrator.** Each round you advance both tracks (spawning a TrackAgent per
lane, spawn-or-degrade), update the scoreboard, and keep both honest. Do not pause for
permission once the loop is running.

The cast and files (all in this folder):
- `roles/TrackAgent.md` — the per-track researcher, instantiated once per lane.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question and wait for the user's answer. Do NOT
infer or skip any.**

### 1.0 Detect host
Check whether `AskUserQuestion` is available. **Yes → Claude Code path** (infer + recommend
via `AskUserQuestion`); **No → plain-text path** (quoted prompts). Record **`<host>`**. Host
also decides spawn-or-degrade: on Claude Code spawn a real `Agent` per lane (the two run in
parallel); otherwise adopt `roles/TrackAgent.md` inline and run the lanes sequentially.

### 1a. Metric (shared)
Record **`<metric>`** and **`<metric_direction>`** (`minimize`/`maximize`). This is shared by
both lanes — it is the ground truth of the duel.

### 1b. Gate (shared)
Record **`<gate>`** = `time` or `epochs` and **`<budget>`**. If `time`, write a
`run_with_timeout.sh` wrapper per lane (`timeout $(( <budget> * 60 )) <entrypoint> "$@"`).

### 1c. Sandbox location (shared)
Record **`<sandbox_root>`** (default `./sandbox/`).

### 1d. Iteration strategy (shared)
Record **`<iter_strategy>`** = `branches` or `snapshots` (snapshots recommended here — two
tracks on one branch is simplest). Each lane snapshots into its own subdir.

Each lane has a **code location** — where its code lives and runs. **We never add code to the
codebase**; a lane is either backed by *existing* repo files or built entirely in the sandbox:

- **`codebase`** — the lane maps to existing code. Record `<run_cmd>` (the existing entrypoint,
  e.g. `python train.py`) and `<editable_files>` (existing repo files it may edit).
- **`sandbox`** — no implementation exists and none is added to the repo. The lane **authors and
  runs its code inside `<sandbox_root>/<lane>/iter<N>/`**. Record `<entry>` — the command run from
  inside that iteration dir (e.g. `python run.py`).

### 1e. Lane A
Record `name` (default **`classical`**), `code_location`, and the fields it requires (above).

### 1f. Lane B
Record `name` (default **`learned`**), `code_location`, and the fields it requires (above).

> **Typical duel on a repo with one existing model (e.g. the testbed's `train.py`):** the
> **learned** lane is `codebase` (edits `model.py`/`config.yaml`, runs `train.py`); the
> **classical** lane is `sandbox` (authors its own code in `<sandbox_root>/classical/iter<N>/`,
> runs it there). Nothing is added to the codebase, yet the classical lane is still built and
> iterated. Two `codebase` lanes must have non-overlapping `editable_files`.

### 1g. Eval-parity check (the honesty anchor)
Confirm **both lanes report `<metric>` on the same held-out set, computed the same way**, so the
scores are comparable. If they don't, fix it before starting — the duel is meaningless otherwise.
State explicitly how each lane emits `<metric>` (e.g. both print `^<metric>:` to their run log).

### 1h. Initialise sandbox
```
<sandbox_root>/
├── schema.yaml          ← resolved bindings (written now)
├── duel_log.md          ← shared channel + scoreboard (written now, headers only)
├── <laneA>/results.tsv  ← lane A experiment ledger, header only
└── <laneB>/results.tsv  ← lane B experiment ledger, header only
```
Each lane's per-iteration work lives in `<sandbox_root>/<lane>/iter<N>/` (`analysis/`,
`results/`, the run log). For a **`codebase`** lane this also holds `code_snapshot/` (the
pre-change copy for revert); for a **`sandbox`** lane it holds the lane's **actual code** for that
iteration (the kept iteration carries forward as the next one's starting point).

**`results.tsv` header** (each lane, tab-separated, no commas):
`iter	<metric>	status	analysis_summary	description`
**`duel_log.md`** starts with a `## Scoreboard` section and a `## Round log` section.
Write all bindings (shared + both lanes) to `schema.yaml`.

### 1i. Confirm and go
Print every resolved binding and the two lanes. **Do not create files or start until the user
confirms.**

---

## 2. The duel loop

Each **round** advances **both** tracks by one iteration. On Claude Code, spawn the two
TrackAgents in parallel; otherwise run lane A then lane B inline. A track is one
`standardMLAutoresearch` iteration confined to its lane — see `roles/TrackAgent.md`.

**Round 1** is each lane's baseline (a `codebase` lane runs unmodified; a `sandbox` lane authors
its initial implementation in `iter1/`). **One change per track per round** (standard attribution).
**FILE EDIT GUARD**: a track edits only its own surface — a `codebase` lane's `<editable_files>`,
or a `sandbox` lane's own `<sandbox_root>/<lane>/` dir. **Never add code to the codebase.**

### LOOP FOREVER:

1. **State.** Note round N. Read `duel_log.md` (both lanes' latest posts + the scoreboard).
2. **Advance each lane.** For each lane, run a **TrackAgent** (`roles/TrackAgent.md`) given its
   lane binding (`name`, `run_cmd`, `editable_files`, `<sandbox_root>/<lane>/`), the shared
   `<metric>`/`<gate>`/`<budget>`, and the current `duel_log.md`. The TrackAgent runs **one
   iteration — the 8 steps in `roles/TrackAgent.md`** (state → hypothesis → snapshot/apply →
   run → read metric → analyse → keep/revert → log), staying in its lane.
3. **Track posts.** Each track appends its round entry to `duel_log.md`: best `<metric>`, one
   key finding, any dead end, one idea the other lane could borrow.
4. **Scoreboard.** Update `## Scoreboard` in `duel_log.md`: best `<metric>` per lane and the
   current leader (per `<metric_direction>`). Optionally flag one cross-pollination suggestion
   (an idea lane X should consider borrowing from lane Y next round).
5. **Go to step 1.**

---

**NEVER STOP**: once running, do not pause to ask "should I continue?". Keep both lanes
iterating indefinitely until manually stopped. Report the **current leader**, never a final
victory — a lane that's behind can still come back, and keeping both honest is the point. If a
lane runs dry, push it to a more radical (in-lane) approach or to borrow a fresh idea from the
log. The loop runs until interrupted.

---

## 3. Ledger formats

**Per-lane `results.tsv`** (tab-separated, never commas) — identical to `standardMLAutoresearch`:
```
iter	<metric>	status	analysis_summary	description
1	0.6320	keep	baseline; classical features, logistic head	baseline
2	0.6610	keep	added HOG features; per-class gains on textured classes	add HOG feature extractor
```

**`duel_log.md`** (shared) — scoreboard + round posts:
```
## Scoreboard
round	classical_best	learned_best	leader
1	0.6320	0.6480	learned
2	0.6610	0.7050	learned

## Round log
### Round 2
- **classical** — best 0.6610 (this iter 0.6610). Finding: HOG helps textured classes
  (results/per_class.txt). Dead end: raw-pixel kNN plateaus. Borrow idea: learned's augmentation
  could expand classical's training set.
- **learned** — best 0.7050. Finding: BN fixed conv2 saturation. Dead end: dropout hurt at this
  budget. Borrow idea: classical's HOG features as an aux input channel.
```

Do not commit `results.tsv`, `duel_log.md`, or `iter*/` to git. Leave them untracked.

---

## 4. Hard constraints (never violate)
- **Never add code to the codebase.** A `codebase` lane edits only its own `<editable_files>`; a
  `sandbox` lane lives entirely in `<sandbox_root>/<lane>/`. Lanes never touch each other's code.
- **Stay in lane**: a track borrows *ideas*, never converts into the other approach.
- Both lanes optimize the **same `<metric>` on the same eval** — never compare otherwise.
- Do not install new packages or add dependencies not already present.
- Do not modify the evaluation/metric — it is the shared ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect each run's output to its lane's run log. Never use `tee`.
- The sandbox is self-contained — no `../` escapes.
- Report the current leader; never declare a final winner while the loop runs.
