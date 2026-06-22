---
name: karpathy
description: >
  Use when the user wants the LLM to do its own ML research: a fully-autonomous loop that hacks the
  training code, runs it, and keeps changes that lower a single scalar metric (e.g. val_bpb). One agent
  proposes one change at a time, runs training in the user's env, keeps it only if the metric improves
  (advancing a git branch) else reverts, and loops forever until the human interrupts. A faithful
  adaptation of Karpathy's autoresearch. Not for the analysis-first variant that profiles before editing
  (that is ml-autoresearch), and not for a budgeted, plateau-stopping refactor.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Karpathy Autoresearch

This is an experiment to have the LLM do its own research. You are a completely autonomous researcher:
you hack the training code with an idea, run it, keep the change if the metric improves and revert it if
it doesn't, advancing a branch as you go — and you repeat **forever, until the human interrupts you.**
The artifact is the `<editable_files>`; the feedback signal is one scalar `<metric>` (lower is better,
e.g. `val_bpb`) read from the run. Training runs in the user's own environment via `<run_cmd>` — this
skill installs nothing and imports nothing; it edits code, shells out, and reads the metric from the log.

## When to use
Use this to leave an agent running on a single training script, optimizing one scalar metric hands-off,
where any improvement is kept and the loop never stops on its own. Default to broad freedom inside
`<editable_files>`; the only hard limit is that the run finishes within the budget without crashing. Not
for the analysis-first variant that reasons about the data before each edit (that is `ml-autoresearch`).

## Setup
Resolve bindings interactively (load `loop.run.yaml` and skip if it already exists; else, on Claude Code
infer + recommend each via `AskUserQuestion`, otherwise ask as quoted prompts; write `loop.run.yaml`).
Then **work with the user** to set up a fresh run:

1. **Choose `<iter_strategy>`** — **branches** (one git commit per run; the original) or **snapshots**
   (one folder per run under `<sandbox_root>/`). Snapshots are safer on a dirty or gitignored tree;
   branches mirror Karpathy. Either is fully supported throughout the loop.
2. **Open the run** — *branches:* agree on a run tag from today's date (e.g. `mar5`) and create the
   branch `git checkout -b autoresearch/<tag>` (it must not already exist; this is a fresh run).
   *snapshots:* no branch — each iteration gets its own `<sandbox_root>/iter<N>/`.
3. **Read the in-scope files** — the repo is small; read them for full context: the README, the
   **read-only** harness that defines the metric (the `<metric>` ground truth — do not modify), and the
   `<editable_files>` you will hack (model/optimizer/training loop).
4. **Verify the env/data exists** — confirm `<run_cmd>` can run (data shards, tokenizer, deps present).
   If not, tell the human the one command to prepare it (e.g. `uv run prepare.py`).
5. **Initialize `results.tsv`** — create it with just the header row; the baseline is recorded after the
   first run. Leave it untracked (never commit it).
6. **Confirm and go** — confirm the setup looks right, then kick off the experimentation.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` | scalar to **minimize**; must be printed by the run (e.g. `val_bpb`) | — | grep the in-scope files / README for `val_bpb`, `val_loss`, `error`… |
| `<run_cmd>` / `<entrypoint>` | the command that launches one training run | — | e.g. `uv run train.py`; from `pyproject.toml`/`.venv`/README |
| `<editable_files>` | the file(s) you may hack — everything else is read-only | — | the training script(s); exclude data, the eval harness, configs you must not touch |
| `<sandbox_root>` | where `results.tsv` (+ snapshots) live | `./sandbox` | — |
| `<iter_strategy>` | `branches` (a git commit per run) or `snapshots` (a folder per run) | `snapshots` | `snapshots` is safer off a dirty/gitignored tree; `branches` mirrors Karpathy |
| `<gate>` / `<budget>` | `time` (wall-clock) or `epochs`, and its value | — | the run's existing time/epoch setting |

## The experiment loop
Each experiment is one training run on a **fixed budget** (`<gate>`/`<budget>` — wall-clock time or a
fixed epoch count, excluding startup/compile). You launch it simply: `<run_cmd>` (e.g. `uv run
train.py`). Because the budget is fixed you don't need to worry about training time — every run gets the
same budget.

**What you CAN do:** Modify `<editable_files>` — this is the only file you edit. Everything is fair
game: model architecture, optimizer, hyperparameters, training loop, batch size, model size, etc.

**What you CANNOT do:** modify the read-only harness or the evaluation (the `<metric>` is the ground
truth); install new packages or add dependencies (use only what's already available).

The goal is simple: get the lowest `<metric>`. Since the budget is fixed, you don't need to worry about
training time — it's always the budget. Everything is fair game: change the architecture, the optimizer,
the hyperparameters, the batch size, the model size. The only constraint is that the code runs without
crashing and finishes within the budget.

VRAM is a soft constraint. Some increase is acceptable for meaningful `<metric>` gains, but it should not
blow up dramatically.

**Simplicity criterion:** All else being equal, simpler is better. A small improvement that adds ugly
complexity is not worth it. Conversely, removing something and getting equal or better results is a great
outcome — that's a simplification win. When evaluating whether to keep a change, weigh the complexity
cost against the improvement magnitude. A 0.001 `<metric>` improvement that adds 20 lines of hacky code?
Probably not worth it. A 0.001 `<metric>` improvement from deleting code? Definitely keep. An improvement
of ~0 but much simpler code? Keep.

**The first run:** Your very first run should always be to establish the baseline, so you will run the
training script as is.

Copy this checklist; **LOOP FOREVER:**
- [ ] **1.** Look at the git state — the branch/commit you're on (snapshots: the next `iter<N>/`).
- [ ] **2.** Tune `<editable_files>` with one experimental idea by directly hacking the code.
- [ ] **3.** Commit it (`git commit -am "<idea>"`; snapshots: copy `<editable_files>` into `iter<N>/code_snapshot/` first).
- [ ] **4.** Run the experiment: `<run_cmd> > run.log 2>&1` (redirect everything — do NOT use `tee` or let output flood your context).
- [ ] **5.** Read the result: `grep "^<metric>:" run.log` (also grab peak memory if printed).
- [ ] **6.** If the grep is empty the run crashed — `tail -n 50 run.log`, read the trace, fix if it's something dumb (typo/missing import), else give up after a couple of tries.
- [ ] **7.** Record the result in `results.tsv` (do NOT commit it — leave it untracked).
- [ ] **8.** If `<metric>` improved (lower), **advance** — keep the commit. 
- [ ] **9.** If it's equal or worse, `git reset` back to where you started (snapshots: restore from `code_snapshot/`). Go to 1.

The idea is that you are a completely autonomous researcher trying things out. If they work, keep. If
they don't, discard. And you're advancing the branch so that you can iterate. If you feel like you're
getting stuck in some way, you can rewind but you should probably do this very very sparingly (if ever).

**Output format.** When the run finishes it prints a summary; the exact lines depend on what the user's
script prints (`<metric>` is whatever you bound — `val_bpb`, `val_loss`, a perplexity, an error rate, …), e.g.:
```
<metric>:         0.997900
peak_vram_mb:     45060.2
num_params_M:     50.3
```
The numbers vary by machine since each run stops at the budget. Extract the metric with
`grep "^<metric>:" run.log`.

**Timeout.** A run should take ~its budget plus a little eval overhead. If a time-gated run exceeds
`2× <budget>` minutes, kill it and treat it as a failure (discard and revert).

**Crashes.** Use judgement: something dumb and easy (a typo, a missing import) — fix it and re-run; an
idea that's fundamentally broken — skip it, log `crash` as the status, and move on.

## results.tsv (logging results)
`<sandbox_root>/results.tsv`, tab-separated (NOT comma-separated — commas break in descriptions). Header
+ 5 columns: the git commit (short, 7 chars; or `iter` in snapshots mode), `<metric>` (e.g. `1.234567`,
or `0.000000` for a crash), peak memory in GB (`.1f`, `peak_vram_mb`/1024; `0.0` for a crash), `status`
∈ {`keep`, `discard`, `crash`}, and a text description of what the experiment tried.
```
commit	<metric>	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
d4e5f6g	0.000000	0.0	crash	double model width (OOM)
```
Report the **best** run when interrupted, not necessarily the last.

## Constraints
- **Only edit `<editable_files>`.** The read-only harness that produces `<metric>` is the ground truth —
  editing it (or the eval) would corrupt the signal the loop is scored against.
- **One change per iteration**, so each `<metric>` delta is attributable to a single idea.
- **Run in the user's env via `<run_cmd>`.** Install nothing, add no dependencies — shell out and read
  the log. Always redirect output to `run.log`; never `tee`, never flood your context.
- **Don't commit `results.tsv`** — leave it untracked. `<sandbox_root>/` is self-contained (no `../`).

## Stops — NEVER STOP
Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should
continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be
asleep, or gone from a computer and expects you to continue working indefinitely until you are manually
stopped. You are autonomous. If you run out of ideas, think harder — read papers referenced in the code,
re-read the in-scope files for new angles, try combining previous near-misses, try more radical
architectural changes. The loop runs until the human interrupts you, period.
