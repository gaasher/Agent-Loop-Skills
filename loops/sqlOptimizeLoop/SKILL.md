---
name: sql-optimize-loop
description: >
  Use when the user wants to iteratively speed up a slow SQL query without changing its results.
  Each iteration rewrites the query or adds an index, benchmarks it against a copy of the database,
  and keeps the change only if it is faster AND returns the same rows as the original; everything
  else is reverted. Loops until a plateau or the iteration budget. Bind it to your database, the
  query file, and a benchmark command at setup. Built around SQLite via the vendored tool; adaptable
  to any engine whose latency and result-set you can measure.
metadata:
  version: "0.1.0"
---

# SQL Optimize Loop

An **evaluator-optimizer** loop. The artifact is a SQL query (and, optionally, a set of indexes);
the feedback signal is two-part: the query must return the **same result-set** as the original (a
hard correctness gate) and its **measured latency must drop** (the thing you minimize). You make one
change, benchmark it, keep it only if it is both correct and faster, and otherwise revert. Repeat
until latency stops improving or the budget runs out.

The signal comes from `tools/bench.py` (vendored, stdlib `sqlite3`): it runs the query against a
**throwaway copy** of the database (so index changes never mutate the seed), times execution over
several repeats, and prints `median_ms` plus a `hash` fingerprint of the rows. **Never edit the
database or `tools/bench.py`** — the data and the measurement are the ground truth.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm the values in one line, and skip to §2. Otherwise
resolve each binding, then write `loop.run.yaml` so re-runs are non-interactive.

**Detect host:** if `AskUserQuestion` is available you are in **Claude Code** — infer a likely value
and present it as the recommended option. Otherwise ask each as a quoted plain-text prompt.

- **`<db>`** — path to the database file (read-only ground truth).
- **`<query_file>`** — the SQL file holding the query to optimize (the primary artifact).
- **`<indexes_file>`** — an optional `.sql` file of DDL (e.g. `CREATE INDEX …`) the loop may add to.
  It is applied to the throwaway copy at benchmark time, so it never alters the seed DB. If the user
  does not want schema changes, leave this unbound and optimize the query text alone.
- **`<bench_cmd>`** — default
  `python3 <skill_dir>/tools/bench.py --db <db> --query <query_file> --setup <indexes_file> --repeat 5`
  (drop `--setup` if no `<indexes_file>`). For a non-SQLite engine, bind any command that prints
  `{"median_ms", "hash"}` for the query so the loop can compare speed and correctness.
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8), **`<patience>`** (default 3).

Example `loop.run.yaml` (see `schema.example.yaml` for a commented template):
```yaml
db: ./test.db
query_file: ./query.sql
indexes_file: ./indexes.sql
bench_cmd: "python3 ../../loops/sqlOptimizeLoop/tools/bench.py --db ./test.db --query ./query.sql --setup ./indexes.sql --repeat 5"
sandbox_root: ./sandbox
budget: 8
patience: 3
```

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip the
confirmation only when `loop.run.yaml` already existed). Then initialise the ledger (§3) and start.

---

## 2. The loop

**Iteration 0 — baseline.** Run `<bench_cmd>` on the unmodified query (and empty/initial
`<indexes_file>`). Record `median_ms` as the current best and **`hash` as the correctness reference
— every later candidate must reproduce this exact `hash`.** Log it. If bench returns an `error`,
stop and report: the query must run before it can be optimized.

**Then, until stop (plateau or budget):**

1. **Snapshot.** Copy `<query_file>` and `<indexes_file>` to `<sandbox_root>/iter<N>/`.
2. **Apply one focused change.** Pick a single optimization idea:
   - **Add an index** to `<indexes_file>` covering the filtered/joined/grouped columns.
   - **Rewrite the query** — e.g. turn a correlated subquery into a `JOIN` + `GROUP BY`, hoist a
     repeated computation, replace `SELECT *` with needed columns, push a filter earlier, remove a
     redundant `DISTINCT`/sort. One idea per iteration so the effect is attributable.
3. **Benchmark.** Run `<bench_cmd>`.
4. **Gate on correctness first.** If the candidate `hash` ≠ the baseline reference `hash` (or bench
   errored), the change altered the results — **discard**: restore `<query_file>`/`<indexes_file>`
   from the snapshot, log `discard` (reason: results changed), continue.
   - *Ordering caveat:* the fingerprint is over the multiset of rows, so it does **not** detect a
     changed row **order**. If the query's `ORDER BY` is part of the contract, eyeball that the
     rewrite preserves it; the hash alone won't catch a reordering.
5. **Gate on speed.** With the hash matching, **keep** only if `median_ms` improves by at least a
   small margin (default ≥3% relative, to clear timing noise); otherwise **discard** and restore.
   On keep, update the best and leave the working files in place.
6. **Log** one ledger row (§3) and continue.

**Stop** when no iteration has set a new best for `<patience>` consecutive iterations, or at
`<budget>`. **Plateau counting:** increment the counter on *every* iteration that does not set a new
best — whether it was discarded for changed results, a broken query, or an insufficient speed gain —
and reset it to 0 on each `keep`. (So `<patience>` failed or fruitless attempts in a row ends the
run; the `<budget>` is the hard cap regardless.) Restore the working files to the **fastest**
iteration and report: baseline vs best `median_ms` (and the speedup factor), the trajectory, and the
winning query + indexes.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the description. Header:
```
iter	median_ms	rows	hash_ok	status	description
```
`status` ∈ {`keep`, `discard`, `baseline`}; `hash_ok` ∈ {`yes`, `no`, `-`}. Example:
```
iter	median_ms	rows	hash_ok	status	description
0	1121.06	10	-	baseline	correlated subquery no index
1	6.82	10	yes	keep	rewrite correlated subquery as JOIN + GROUP BY
2	1.18	10	yes	keep	add index orders(customer_id, amount)
3	1.20	10	yes	discard	add index orders(status) — no gain
4	0.40	10	no	discard	drop ORDER BY — changed result set
```
Report the **fastest** iteration, not necessarily the last.

---

## 4. Hard constraints
- **Only edit `<query_file>` and `<indexes_file>`.** The database and `tools/bench.py` are read-only
  ground truth; changing the data or the measurement invalidates the run.
- **Correctness gate is non-negotiable** — a faster query that changes the result-set is a
  regression, not an optimization. Match the baseline `hash` every time.
- **One change per iteration**, so each latency change is attributable.
- Benchmark every candidate the same way (same `--repeat`); compare `median_ms`, not a single run.
- The sandbox is self-contained — no `../` escapes beyond the bound `<sandbox_root>`.
- Do not pause the loop to ask whether to continue; run until plateau or budget.
