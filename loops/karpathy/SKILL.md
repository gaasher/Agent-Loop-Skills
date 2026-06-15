---
name: karpathy
description: >
  Use when the user wants a fully-autonomous, iterate-and-score research loop
  modelled on Karpathy's autoresearch program. One agent hacks code, runs it,
  and keeps changes that improve a user-defined scalar metric — looping forever
  until manually interrupted.
metadata:
  version: "0.1.0"
---

# Karpathy Autoresearch Loop

This is an autonomous research loop. You propose changes, run them, keep the
ones that improve the metric, discard the rest, and repeat — forever, until the
human interrupts you. You are the researcher. Do not pause to ask for permission
once the loop is running.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. You MUST ask every question below and wait for the
user's explicit answer before proceeding. Do NOT skip or auto-apply any answer —
even if you can read the files and think you already know the value. The purpose of
asking is to put the user in control of their experiment. If you skip any question,
you are doing it wrong.**

### 1.0 Detect host

Check whether the `AskUserQuestion` tool is available to you.

- **If yes** → you are running in **Claude Code**. Use the **Claude Code path** for
  every question below: scan the project first to infer a likely answer, then present
  it as the recommended option via `AskUserQuestion`. The user confirms or overrides
  with one click.
- **If no** → use the **plain-text path**: ask each question as a quoted prompt and
  wait for the user's typed reply.

Record as **`<host>`** = `claude-code` or `other`. Proceed to 1a.

---

### 1a. What metric should the loop minimize?

**Claude Code**: Scan `<editable_files>` and any README for metric names
(`val_loss`, `val_acc`, `bpb`, `error`, etc.). Call `AskUserQuestion`:
- Option 1 *(Recommended)*: the value you inferred, e.g. `val_acc`
- Option 2–3: other plausible metrics you spotted
- Option 4: `Other — I'll specify`

**Other**: Ask:
> "What scalar metric should I minimize? (e.g. `val_loss`, `val_bpb`, `error_rate`)"

Record as **`<metric>`**. The loop infers the grep pattern automatically — tries
`^<metric>:` first; if that returns nothing, scans `tail -n 20 run.log` and locks
in the correct pattern.

---

### 1b. What Python environment should be used?

**Claude Code**: Scan for `pyproject.toml`, `.venv/`, `uv.lock`, virtualenv paths,
and any README run instructions to infer the run command. Call `AskUserQuestion`:
- Option 1 *(Recommended)*: the command you inferred, e.g.
  `/path/to/venv/bin/python train.py`
- Option 2: `uv run train.py`
- Option 3: `Other — I'll specify`

**Other**: Ask:
> "What Python environment / uv project should I use to run training?
>  (e.g. `uv run train.py`, or a path to a virtualenv + script)"

Record as **`<run_cmd>`**.

> **Remote sandboxes**: if the sandbox is on a remote host (SSH, cloud VM, container),
> note the connection details. All shell commands below are issued through that
> connection. The loop runs locally; only `<run_cmd>` is dispatched remotely if needed.

---

### 1c. Which files are fair game to edit?

**Claude Code**: List every source file that looks like a primary artifact (model
definition, config, training script) — exclude data, logs, env files, and the
evaluation harness. Call `AskUserQuestion` (multi-select if supported):
- One option per candidate file you found, e.g. `model.py`, `config.yaml`,
  `train.py`
- A final option: `Other — I'll specify`

**Other**: Ask:
> "Which files may I edit? List them. (Typical answer: just `train.py`, or a set of
>  model/config files.)"

Record as **`<editable_files>`**.

**IMPORTANT — file edit guard**: Before touching any file at any point in this
session — setup or loop — verify it appears in `<editable_files>`. If it does not,
do not edit it under any circumstances. Every other file is read-only.

---

### 1d. What is the training entrypoint?

**Claude Code**: Check if the entrypoint is the same as `<run_cmd>` — it usually is.
Call `AskUserQuestion`:
- Option 1 *(Recommended)*: `Same as run command — <run_cmd>`
- Option 2: `Other — I'll specify`

**Other**: Ask:
> "What command starts a single training run? Is it the same as your run command,
>  or a separate script?"

Record as **`<entrypoint>`** (often the same as `<run_cmd>`).

---

### 1e. Where should the sandbox live?

**Claude Code**: Propose a sensible default (e.g. `./sandbox/` next to the
editable files, or a path from any README). Call `AskUserQuestion`:
- Option 1 *(Recommended)*: the path you inferred, e.g. `./sandbox`
- Option 2: `Other — I'll specify`

**Other**: Ask:
> "Where should I keep the sandbox (results log + per-iteration snapshots)?
>  Give me an absolute path. If training runs on a remote host, tell me whether
>  the sandbox should be local or remote."

Record as **`<sandbox_root>`**.

---

### 1f. Iteration strategy — branches or same-branch snapshots?

**Claude Code**: Check whether the working directory is a git repo and whether it is
gitignored/excluded from the main tree (suggesting snapshots is safer). Call
`AskUserQuestion`:
- Option 1 *(Recommended)*: whichever you inferred is safer, with a one-line reason
- Option 2: the other strategy

**Other**: Ask:
> "How should I track iterations?
>  (a) **Branch per iteration** (Karpathy original): each experiment gets a git commit
>      on a dedicated `autoresearch/<tag>` branch; good runs advance the branch,
>      bad runs are `git reset`'d.
>  (b) **Same-branch snapshots**: all work stays on the current branch; each iteration
>      gets a folder under the sandbox with a code snapshot."

Record as **`<iter_strategy>`** = `branches` or `snapshots`.

**If `branches`**: propose a run tag based on today's date (e.g. `jun14`). The branch
`autoresearch/<tag>` must not already exist. Create it: `git checkout -b autoresearch/<tag>`.

**If `snapshots`**: the sandbox layout will be:
```
<sandbox_root>/
├── results.tsv
└── iter1/
    └── code_snapshot/
```

---

### 1g. Gate on time or epochs?

**Claude Code**: Check the training script and config for any existing time or epoch
setting to infer a sensible default. Call `AskUserQuestion`:
- Option 1 *(Recommended)*: `epochs — <N> per run` (if you found an epoch count)
- Option 2: `time — <M> minutes per run` (if you found a time budget)
- Option 3: `Other — I'll specify`

**Other**: Ask:
> "Should each training run be gated by **wall-clock time** (e.g. 5 minutes) or
>  by a fixed **number of epochs**?"

Record as **`<gate>`** = `time` or `epochs`.

**If `time`**:
- *(Claude Code)*: `AskUserQuestion` — "How many minutes per run?" with inferred
  value as recommended option.
- *(Other)*: Ask: "How many minutes per run?"
- Record as **`<budget_minutes>`**. If `<entrypoint>` does not already enforce a time
  budget, write a wrapper to `<sandbox_root>/run_with_timeout.sh`:
  ```bash
  #!/usr/bin/env bash
  timeout $(( <budget_minutes> * 60 )) <entrypoint> "$@"
  ```
  Use that wrapper as the effective run command. Hard kill at `2 × <budget_minutes>`
  minutes — treat as crash if exceeded.

**If `epochs`**:
- *(Claude Code)*: `AskUserQuestion` — "How many epochs per run?" with inferred value
  as recommended option.
- *(Other)*: Ask: "How many epochs per run?"
- Record as **`<budget_epochs>`**. If needed, patch the file in `<editable_files>` that
  controls epochs to cap at `<budget_epochs>`. Do not touch files outside
  `<editable_files>`.

### 1h. Read in-scope files

Read every file in `<editable_files>` now for full context before the first run.

### 1i. Initialise results.tsv

Create `<sandbox_root>/results.tsv` with just the header row (tab-separated — do NOT
use commas, they break in description text):

**snapshots mode**:
```
iter	<metric>	status	description
```

**branches mode**:
```
commit	<metric>	status	description
```

Do not commit `results.tsv` to git — leave it untracked.

### 1j. Write the run schema to the sandbox

Write all resolved values to **`<sandbox_root>/schema.yaml`** so the run is
reproducible. Example shape (substitute real values):

```yaml
metric: val_loss
run_cmd: "uv run train.py"
entrypoint: "uv run train.py"
editable_files:
  - train.py
sandbox_root: /path/to/sandbox
iter_strategy: snapshots   # or: branches
run_tag: jun14             # branches mode only
gate: time
budget_minutes: 5          # time mode
# budget_epochs: 10        # epochs mode
```

This file is written once at setup. A copy is also placed inside each `iter<N>/`
folder so every iteration is self-contained and auditable.

### 1k. Confirm and go

Print a summary of every resolved binding and ask the user to confirm before doing
anything else. **Do not create any files, directories, or sandbox structures until the
user has confirmed.** Once they confirm, set up the sandbox (§1e–§1i) and begin the
loop immediately.

---

## 2. The experiment loop

**Everything in `<editable_files>` is fair game**: change the architecture, the
optimizer, the hyperparameters, the batch size, the model size. The only constraint is
that the code runs without crashing and finishes within the budget. Everything else is
up to you.

**VRAM / memory** is a soft constraint. Some increase is acceptable for meaningful
`<metric>` gains, but it should not blow up dramatically.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement
that adds ugly complexity is not worth it. Conversely, removing something and getting
equal or better results is a great outcome — that's a simplification win. When
evaluating whether to keep a change, weigh the complexity cost against the improvement
magnitude. A 0.001 improvement that adds 20 lines of hacky code? Probably not worth it.
A 0.001 improvement from *deleting* code? Definitely keep. An improvement of ~0 but
much simpler code? Keep.

**The first run**: Your very first run should always be to establish the baseline — run
the training script as-is, without any changes.

**FILE EDIT GUARD**: Before editing *any* file at *any* step below, confirm the file is
in `<editable_files>`. If it is not, do not edit it. No exceptions.

---

### LOOP FOREVER:

**1. Look at the git/sandbox state.**

- *branches mode*: run `git log --oneline -5` and note the current branch and commit
  hash (short, 7 chars).
- *snapshots mode*: note the current iteration number N and confirm
  `<sandbox_root>/iter<N>/` does not already exist.

**2. Tune `<editable_files>` with an experimental idea by directly hacking the code.**

For the very first run, skip this — run the script unmodified to establish the
baseline.

For every subsequent run, pick one focused experimental idea (what to try and why),
then edit the relevant file(s) in `<editable_files>`. Keep changes focused — one idea
per iteration.

- *snapshots mode*: before editing anything, create `<sandbox_root>/iter<N>/` and copy:
  - every file in `<editable_files>` → `<sandbox_root>/iter<N>/code_snapshot/` (preserving relative paths)
  - `<sandbox_root>/schema.yaml` → `<sandbox_root>/iter<N>/schema.yaml`

  Then apply your changes to the working files.

**3. Commit (branches mode) / snapshot already taken (snapshots mode).**

- *branches mode*: `git commit -am "<short description of idea>"`
- *snapshots mode*: snapshot was taken in step 2; nothing extra to do here.

**4. Run the experiment — redirect everything, do NOT use `tee` or let output flood your context.**

```bash
# time-gated
<sandbox_root>/run_with_timeout.sh > <sandbox_root>/iter<N>/run.log 2>&1

# epoch-gated
<entrypoint> > <sandbox_root>/iter<N>/run.log 2>&1
```

If the run has not terminated when it should have, kill it and treat it as a crash —
discard and revert.

**5. Read out the results.**

```bash
grep '^<metric>:' <sandbox_root>/iter<N>/run.log
```

If that returns nothing, scan `tail -n 20 run.log` to find where the value is printed
and use that pattern going forward.

**6. If the grep output is empty, the run crashed.**

```bash
tail -n 50 <sandbox_root>/iter<N>/run.log
```

Read the Python stack trace and attempt a fix. Use your judgement:
- If it's something dumb and easy to fix (a typo, a missing import), fix it — edit only
  files in `<editable_files>` — and re-run once. Do not re-run more than a few times.
- If the idea itself is fundamentally broken, skip it, log `crash` in the TSV, and
  move on.

**7. Record the results in `results.tsv`. Do NOT commit this file — leave it untracked.**

Append one tab-separated row:

- *snapshots mode*: `<N>  <metric_value>  <status>  <short description>`
- *branches mode*: `<commit>  <metric_value>  <status>  <short description>`

`<status>` ∈ {`keep`, `discard`, `crash`}. Use `0.000000` for the metric on crashes.

**8. Keep or revert.**

- **If `<metric>` improved** (lower is better — lower than the current best):
  - Status → `keep`. Update your current-best record.
  - *branches mode*: stay on this commit — the branch advances.
  - *snapshots mode*: leave the working files as-is.

- **If `<metric>` is equal or worse** (or a crash):
  - Status → `discard` (or `crash`).
  - *branches mode*: `git reset --hard HEAD~1` to revert.
  - *snapshots mode*: restore every file in `<editable_files>` from
    `<sandbox_root>/iter<N>/code_snapshot/` back to the working directory.

  The idea is that you are a completely autonomous researcher trying things out. If they
  work, keep. If they don't, discard. You advance by keeping good commits / snapshots
  and reverting bad ones. If you feel stuck, you can rewind further, but do this very
  sparingly (if ever).

**→ Go back to step 1 for iteration N+1.**

---

**Timeouts**: each experiment should take roughly `<budget>` (+ a few seconds for
startup and eval overhead). If the run has not terminated when it should have, kill it
and treat it as a failure — discard and revert.

**Crashes**: if a run crashes (OOM, a bug, etc.), use your judgement. If it's something
dumb and easy to fix (a typo, a missing import), fix it and re-run. If the idea itself
is fundamentally broken, just skip it, log `crash`, and move on.

**NEVER STOP**: Once the experiment loop has begun (after setup), do NOT pause to ask
the human if you should continue. Do NOT ask "should I keep going?" or "is this a good
stopping point?". The human might be asleep, or away from their computer, and expects
you to continue working **indefinitely** until manually stopped. You are autonomous. If
you run out of ideas, think harder — re-read the in-scope files for new angles, try
combining previous near-misses from `results.tsv`, try more radical architectural
changes. The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each
experiment takes `<budget_minutes>` minutes, you can run ~`60/<budget_minutes>` per
hour — roughly 100 experiments over a typical night. The user wakes up to a full
`results.tsv` of completed experiments.

---

## 3. results.tsv format

Tab-separated. Never use commas in descriptions.

**snapshots mode**:
```
iter	<metric>	status	description
1	0.997900	keep	baseline
2	0.993200	keep	increase LR to 0.04
3	1.005000	discard	switch to GeLU activation
4	0.000000	crash	double model width (OOM)
```

**branches mode**:
```
commit	<metric>	status	description
a1b2c3d	0.997900	keep	baseline
b2c3d4e	0.993200	keep	increase LR to 0.04
c3d4e5f	1.005000	discard	switch to GeLU activation
d4e5f6g	0.000000	crash	double model width (OOM)
```

---

## 4. Hard constraints (never violate)

- **Only edit files in `<editable_files>`.** Before touching any file, confirm it is in
  this list. Everything else is read-only — no exceptions.
- Do not install new packages or add dependencies not already present in the project.
- Do not modify the evaluation harness — `<metric>` is the ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect training output to `run.log`. Never use `tee`. Never let output flood
  your context.
- The sandbox (`<sandbox_root>/`) must be fully self-contained — no `../` path escapes.
- Do not commit `results.tsv` to git. Leave it untracked.
