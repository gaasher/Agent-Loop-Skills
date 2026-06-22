---
name: optimize-loop
description: >
  Use when the user wants to iteratively improve an artifact under a hard correctness bound while
  minimizing a measured cost — refactoring a code module to cut complexity while its test suite stays
  green, OR speeding up a SQL query while it returns the same rows. Each iteration applies one focused
  change, checks a correctness gate that must pass, measures a metric that must drop, and keeps the
  change only if both hold, else reverts; loops to a plateau or budget. Not for adding features,
  fixing bugs, or any change that is allowed to alter behaviour or results.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---
# Optimize Loop

An **evaluator-optimizer** loop with a **pluggable correctness gate + minimized metric**. The artifact
is some editable thing (a code module or a SQL query); the feedback signal is two-part: a **bound gate
that must pass** (behaviour/results unchanged) and a **bound metric that must drop** (the cost you
minimize). You apply one change, check the gate, measure the metric, and keep the change only if the
gate passes AND the metric improves — otherwise you revert. Repeat until the metric stops improving or
the budget runs out. Once the loop starts, do not pause for permission.

Two ready bindings ship in `tools/` (both vendored, stdlib-only):
- **code mode** — gate: `<gate_cmd>` (the test suite) exits 0; metric: `tools/metrics.py` prints
  `complexity` (primary), `max_nesting`, `loc` (lexicographic tie-breakers). Lower is better.
- **sql mode** — gate: the result-set `hash` from `tools/bench.py` matches the baseline; metric: the
  same tool's `median_ms`. Lower is better.

The gate is non-negotiable in both modes: a change that fails it is a regression, not an improvement.
Never edit the ground truth (the tests / `tools/metrics.py` in code mode, the database / `tools/bench.py`
in sql mode) — editing what measures you to move the number defeats the loop.

## When to use
Use when there is a clear correctness bound to *hold* and a number to *minimize*: refactoring code that
has a passing test suite (cut complexity), or tuning a SQL query that has a fixed result-set (cut
latency). The default is the matching shipped tool; the escape hatch is to bind any `<gate_cmd>` that
exits 0 on pass and any `<metric_cmd>` that prints a single number to minimize (e.g. a linter's issue
count, or a non-SQLite engine's timing + result fingerprint). Not for adding features or fixing
bugs — those *intend* to change behaviour, which this loop is built to forbid.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values back in one line, and skip to the loop. Otherwise pick `<mode>` first (it selects the gate +
metric), then on Claude Code (the `AskUserQuestion` tool is available) infer a likely value for each
binding and present it as the recommended option; on other hosts ask each as a quoted plain-text
prompt. Then write `loop.run.yaml` and confirm the values before creating any other files.

`<gate_cmd>` and `<metric_cmd>` are the pluggable core: bind them per `<mode>` from the table. In sql
mode one bench command supplies both — its `hash` is the gate, its `median_ms` is the metric.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<mode>` | `code` (refactor under test) or `sql` (query, fixed results) | — | the artifact's kind |
| `<editable_files>` | the file(s) the loop may change | — | code: source files (not tests/configs/the tool); sql: the query file (+ optional indexes file) |
| `<gate_cmd>` | the **bound gate** that must PASS, else revert | — | code: the test command (exits 0 on pass); sql: implicit — candidate `hash` must equal the baseline `hash` from the bench command |
| `<metric_cmd>` | the **bound metric** printing a number to minimize | — | code: `python3 <skill_dir>/tools/metrics.py <editable_files>` (→ `complexity`, then `max_nesting`, `loc`); sql: `python3 <skill_dir>/tools/bench.py --db <db> --query <query_file> --setup <indexes_file> --repeat 5` (→ `median_ms`, `hash`) |
| `<sandbox_root>` | where snapshots + the ledger live | `./sandbox` | — |
| `<budget>` | max iterations (hard cap) | 8 | — |
| `<patience>` | stop after N consecutive no-improvement iterations | 3 | — |

`<skill_dir>` is this skill's installed folder; substitute the real path when writing `loop.run.yaml`.
For non-default engines/languages, bind any `<gate_cmd>`/`<metric_cmd>` meeting the contract above.
Two worked configs: `examples/refactor.run.yaml` (code) and `examples/sql.run.yaml` (sql).

## The loop (until plateau or `<budget>`)
Copy this checklist and tick items off:
- [ ] Iteration 0 — baseline: run `<gate_cmd>` (code) — if not green, stop (the loop needs a passing
      gate to protect behaviour). Run `<metric_cmd>`; record the metric as the current best, and in
      sql mode record the baseline `hash` as the correctness reference. Log the baseline row.
- [ ] Snapshot every file in `<editable_files>` to `<sandbox_root>/iter<N>/` so the iteration reverts.
- [ ] Apply **one** focused change (see the per-mode ideas below) — one idea per iteration so each
      metric delta is attributable.
- [ ] Check the gate: code — run `<gate_cmd>`; sql — read the candidate's `hash` from `<metric_cmd>`.
- [ ] If the gate fails (tests non-zero / `hash` ≠ baseline / the tool errored), **discard**: restore
      from the snapshot, log the reason, continue.
- [ ] Measure the metric and compare to the best: code — the triple `(complexity, max_nesting, loc)`
      **lexicographically** (complexity first; only on a tie consult `max_nesting`, then `loc`); sql —
      `median_ms`, keeping only on a margin clear of timing noise (default ≥ 3% relative).
- [ ] **Keep** if the metric strictly improves the best (update the best, leave the files in place),
      else **discard** (restore from the snapshot).
- [ ] Append a ledger row; stop on plateau (`<patience>`) or `<budget>`.

**Change ideas — code mode:** flatten nested `if/else` into guard clauses, replace a hand-rolled loop
with a stdlib call (`sum`, `min`, `max`, `statistics.*`), collapse duplicated branches, remove dead
code. Preserve public behaviour — names, signatures, return shapes, raised exceptions; the test suite
is the contract.

**Change ideas — sql mode:** add an index to `<indexes_file>` covering filtered/joined/grouped columns;
rewrite the query (correlated subquery → `JOIN` + `GROUP BY`, hoist a repeated computation, replace
`SELECT *` with needed columns, push a filter earlier, drop a redundant `DISTINCT`/sort). The `hash` is
over the multiset of rows, so it does **not** catch a changed row **order** — if `ORDER BY` is part of
the contract, eyeball that the rewrite preserves it.

**Lexicographic keep (code mode), current best `(18, 3, 64)`:** `(15, 3, 45)` keep (lower complexity);
`(18, 2, 70)` keep (tie complexity, lower nesting); `(18, 3, 61)` keep (tie, fewer lines); `(18, 3, 64)`
discard (no progress); `(19, 1, 20)` discard (higher complexity outweighs simpler nesting/loc).

**Plateau counting:** increment the no-improvement counter on *every* iteration that does not set a new
best — discarded for a failed gate, a broken change, or an insufficient metric gain — and reset it to 0
on each keep. `<patience>` fruitless iterations in a row ends the run; `<budget>` is the hard cap. On
stop, restore the working files to the **best** iteration (if the latest was a discard) and report:
baseline vs best metric (and, in sql mode, the speedup factor), the trajectory, and the winning change
set. If you run low on ideas before the budget, look harder rather than stopping early.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the description. `status` ∈
{`keep`, `discard`, `baseline`}. Use the columns for the active `<mode>`.

Code mode header `iter	complexity	max_nesting	loc	status	description`:
```
iter	complexity	max_nesting	loc	status	description
0	23	7	86	baseline	unmodified module
1	19	5	78	keep	flatten summarize guard clauses
2	19	5	80	discard	extract helper (no complexity gain)
3	13	3	40	keep	use statistics + min/max/median
```
SQL mode header `iter	median_ms	rows	hash_ok	status	description` (`hash_ok` ∈ {`yes`,`no`,`-`}):
```
iter	median_ms	rows	hash_ok	status	description
0	1121.06	10	-	baseline	correlated subquery no index
1	6.82	10	yes	keep	rewrite correlated subquery as JOIN + GROUP BY
2	1.18	10	yes	keep	add index orders(customer_id, amount)
4	0.40	10	no	discard	drop ORDER BY — changed result set
```
Report the **best** iteration, not necessarily the last.

## Constraints
- **Only edit files in `<editable_files>`** — the gate's ground truth is read-only: the tests and
  `tools/metrics.py` (code), the database and `tools/bench.py` (sql). Editing what measures you to move
  the number invalidates the run.
- **The correctness gate is non-negotiable.** A change that fails it (tests red, or `hash` ≠ baseline)
  is a regression, not an optimization — revert it regardless of the metric. A green gate after a
  behaviour change means the gate is too weak, not that the change is safe; prefer holding behaviour
  identical over trusting a thin gate.
- **One change per iteration**, so each metric delta is attributable.
- **Measure every candidate the same way** (code: the same `<gate_cmd>`; sql: the same `--repeat`);
  compare the metric, not a single noisy run.
- Keep changes within the existing dependency set; do not add imports the project lacks (stdlib is fine).
- The sandbox is self-contained — no `../` escapes beyond the bound `<sandbox_root>`.
- Do not pause the loop to ask whether to continue; run until plateau or budget.
