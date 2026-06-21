---
name: code-refactor-loop
description: >
  Use when the user wants to iteratively refactor a code module — improving readability and
  cutting complexity while a test suite stays green. Each iteration applies one focused refactor,
  runs the tests (a hard gate) and a complexity metric, and keeps the change only if the tests
  still pass AND complexity drops; it reverts everything else. Loops until a plateau or the
  iteration budget. Bind it to your files, your test command, and a metric command at setup.
metadata:
  version: "0.1.0"
---

# Code Refactor Loop

An **evaluator-optimizer** loop. The artifact is a code module; the feedback signal is two-part:
the **test suite must stay green** (a hard gate — behaviour is the contract) and a **complexity
score must drop** (the thing you minimize). You apply one refactor, measure, keep it only if it
both passes the tests and lowers complexity, and otherwise revert. You repeat until the score
stops improving or the budget runs out. You are the refactorer; once the loop starts, do not pause
for permission.

The signal comes from `tools/metrics.py` (vendored, stdlib-only): it reports summed cyclomatic
`complexity` (primary), `max_nesting` and `loc` (tie-breakers) for the target files. Lower is
better. **Never edit the tests or `tools/metrics.py`** — they are the ground truth; editing them
to move the number defeats the loop.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` already exists in the working directory, load it, confirm the values back to
the user in one line, and skip to §2. Otherwise resolve each binding below, then write
`loop.run.yaml` so the run is reproducible and re-runs are non-interactive.

**Detect host:** check whether `AskUserQuestion` is available. If yes you are in **Claude Code** —
infer a likely value for each binding and present it as the recommended option via
`AskUserQuestion`. If no, ask each as a quoted plain-text prompt and wait for the reply.

- **`<editable_files>`** — the module(s) to refactor. *Claude Code:* list source files that look
  like primary artifacts (exclude tests, configs, the metric tool) and offer them multi-select.
  *Other:* "Which file(s) may I refactor?" Everything else is read-only.
- **`<test_cmd>`** — the command that runs the behaviour tests, exiting non-zero on failure
  (e.g. `python3 -m unittest`, `pytest -q`, `npm test`). This is the hard gate.
- **`<metric_cmd>`** — how to score complexity. Default:
  `python3 <skill_dir>/tools/metrics.py <editable_files>` where `<skill_dir>` is this skill's
  folder. It prints JSON with a `complexity` field. For non-Python code, bind any command that
  prints a single number to minimize (e.g. a linter's issue count); the loop only needs "lower is
  better".
- **`<sandbox_root>`** — where snapshots + the ledger live (default `./sandbox/`).
- **`<budget>`** — max iterations (default 8). **`<patience>`** — stop after this many consecutive
  iterations with no improvement (default 3).

Write `loop.run.yaml`:
```yaml
editable_files: [code/messy_stats.py]
test_cmd: "python3 -m unittest"
metric_cmd: "python3 ../../loops/codeRefactorLoop/tools/metrics.py code/messy_stats.py"
sandbox_root: ./sandbox
budget: 8
patience: 3
```

**Confirm and go.** Print the resolved bindings. Do not create files until the user confirms (skip
this confirmation only when `loop.run.yaml` already existed). Then initialise the ledger (§3) and
start.

---

## 2. The loop

**Iteration 0 — baseline.** Run `<test_cmd>`. If it is not green, stop and report: the loop needs a
passing suite to protect behaviour. Run `<metric_cmd>` and record the baseline `complexity` as the
current best. Log it.

**Then, until stop (plateau or budget):**

1. **Snapshot.** Copy every file in `<editable_files>` to
   `<sandbox_root>/iter<N>/code_snapshot/` (preserving relative paths) so the iteration is revertible.
2. **Apply one focused refactor.** Pick a single idea that should reduce complexity without changing
   public behaviour — e.g. flatten nested `if/else` into guard clauses, replace a hand-rolled loop
   with a stdlib call (`sum`, `min`, `max`, `statistics.*`), collapse duplicated branches, remove
   dead code. One idea per iteration so the effect is attributable.
3. **Gate on tests.** Run `<test_cmd>`.
   - **Fails** → the refactor changed behaviour or broke the code. Restore `<editable_files>` from
     the snapshot, log `discard` (reason: tests), go to the next iteration.
4. **Score.** Run `<metric_cmd>` and read `complexity`, `max_nesting`, `loc`. Compare the triple
   `(complexity, max_nesting, loc)` against the current best **lexicographically**: compare
   `complexity` first; only if it ties, compare `max_nesting`; only if that also ties, compare `loc`.
   - **The triple is smaller** → `keep`: update the best, leave the working files as they are.
   - **Otherwise** (equal or larger) → `discard`: restore from the snapshot.

   Worked examples (current best = `(18, 3, 64)`):
   - `(15, 3, 45)` → **keep** — lower complexity wins outright.
   - `(18, 2, 70)` → **keep** — same complexity, lower nesting (loc is not even consulted).
   - `(18, 3, 61)` → **keep** — same complexity and nesting, fewer lines.
   - `(18, 3, 64)` → **discard** — identical triple, no progress.
   - `(19, 1, 20)` → **discard** — higher complexity outweighs the simpler nesting/loc.
5. **Log** one ledger row (§3) and continue.

**Stop** when `complexity` has not improved for `<patience>` consecutive iterations, or at
`<budget>`. Restore the working files to the **best** iteration if the latest was a discard, and
report: starting vs best `complexity`, the trajectory, and which refactors landed.

**If you run low on ideas before the budget**, look harder — re-read the module for remaining
nesting, repeated expressions, or anything the stdlib already does — rather than stopping early.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the description. Header:
```
iter	complexity	max_nesting	loc	status	description
```
`status` ∈ {`keep`, `discard`, `baseline`}. Example:
```
iter	complexity	max_nesting	loc	status	description
0	23	7	86	baseline	unmodified module
1	19	5	78	keep	flatten summarize guard clauses
2	19	5	80	discard	extract helper (no complexity gain)
3	13	3	40	keep	use statistics + min/max/median
```
Report the **best** iteration, not necessarily the last.

---

## 4. Hard constraints
- **Only edit files in `<editable_files>`.** Tests and `tools/metrics.py` are read-only ground
  truth; editing them to move the number invalidates the run.
- **Preserve public behaviour** — names, signatures, return shapes, raised exceptions. The test
  suite is the contract; a green suite after a behaviour change means the tests are too weak, not
  that the refactor is safe — prefer keeping behaviour identical over trusting a thin suite.
- **One refactor per iteration**, so each complexity change is attributable.
- Keep changes within the existing dependency set; do not add imports the project does not already
  have (stdlib is fine).
- The sandbox is self-contained — no `../` escapes beyond the bound `<sandbox_root>`.
- Do not pause the loop to ask whether to continue; run until plateau or budget.