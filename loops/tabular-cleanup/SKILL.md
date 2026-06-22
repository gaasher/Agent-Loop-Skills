---
name: tabular-cleanup
description: >
  Use when the user has a messy tabular data dump (CSV/TSV/parquet/Excel/JSON) and wants it
  iteratively cleaned to an inferred data contract — a checklist of deterministic pass/fail
  checks, not a quality score. A single agent profiles the table, synthesizes a per-column
  contract compiled into binary checks (types, nulls, duplicates, inconsistent categories,
  format/range violations, outliers), then applies one targeted transform at a time, keeping it
  only if it reduces its target check's violations with no regression and no guardrail breach.
  Stops deterministically when every check passes, every remaining check is an unfixable
  residual, or a budget is hit; emits a replayable pipeline and an auditable ledger. Not for
  open-ended analysis of an already-clean dataset, diagnosing one known anomaly, or verifying a
  claim against sources — those are analytical loops; this rewrites the data to a contract.
compatibility: Requires Python 3.9+
metadata:
  version: "0.2.0"
---

# Tabular Cleanup Loop

A **single agent** that takes a messy data dump (`<artifact>`) to the cleanest defensible state,
**no human in the loop** once running. The objective is a **checklist, not a score**: the agent
infers a data contract, compiles it into **deterministic binary checks** (each reports a
violation *count*, never a weighted float), then each iteration profiles the table, picks the
worst open check, applies **one** pandas transform to resolve it, and keeps it only if that
check's violations strictly drop with no collateral damage. Every accepted transform appends to
a replayable `pipeline.py`; every attempt logs to the `ledger`. The work decomposes into
**structure** (parse correctly, one tidy table, sane types) → **contract synthesis** (turn every
observed anomaly into a check) → **the fix loop**. Contract synthesis is where quality is won or
lost: an issue the profiler notices but never compiles into a check (classically, many spellings
of one category) silently survives — a green checklist over dirty data. Checks read the *stored*
value, so canonicalization is real work the loop must do, not a check-time trick.

## When to use

Use this to autonomously clean a messy table to an inferred, confirmed contract where every
defect is a deterministic check the loop must drive to zero or to an honest residual. Default to
strict contract inference (a lenient contract that lets dirty data go "all green" fast is the
primary failure mode); the only human checkpoint is confirming the contract at setup, after
which the loop runs to a stop condition. Not for open-ended discovery over an already-clean
dataset, diagnosing one known anomaly, or checking an external claim against sources — those are
analytical loops; this one **rewrites the data** to match a contract.

## Setup

Resolve bindings interactively. If `loop.run.yaml` exists in the working dir, load it, confirm
the values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion`
tool is available) infer a likely value for each binding and present it as the recommended
option; on other hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml`
(format: `examples/run.example.yaml`) and confirm the values before creating any other files.
**The contract (below) is the one decision the user must actively approve** — infer it, then get
explicit sign-off; everything after is autonomous.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<artifact>` | messy table to clean; **READ-ONLY** (v0 is a copy) | — | scan the working dir for a data file; detect `<format>` + delimiter/encoding/header/quote from the extension |
| `<contract>` | inferred per-column contract + cross-column rules + guardrails; the sole authority for "correct" | — | profile the raw artifact, then synthesize (see below) and confirm |
| `<retention_floor>` | cumulative `unique_rows_kept / unique_rows_in_v0` must stay ≥ this (denominator is v0 *deduped*) | `0.95` | — |
| `<protected_columns>` | columns that must survive; dropping one needs explicit allowance | all (`*`) | — |
| `<impute_cap>` | max fraction of a column's cells that may be *imputed* (synthetic substitute inserted) | `0.20` | — |
| `<analysis_cmd>` | interpreter that runs profiling/transform code in the user's env (has pandas) | `python3` | `pyproject.toml`/`.venv`/`uv` in the working dir |
| `<sandbox_root>` | where `tcl/` (versions, transforms, profiles, ledger, pipeline) lives | `./sandbox` | — |
| `<gate>` / `<budget>` | backstop only: `iterations`/`tokens`/`time` and its cap | `iterations` / `30` | — |

Profiling and transform code run in the **user's environment** via `<analysis_cmd>`, so they may
use pandas. Keep helper code **stdlib-first**: probe heavy imports with `try/except ImportError`
and degrade, or offer a consented `uv pip install "pandas==<ver>"` — never assume it is present.

### Contract synthesis (the make-or-break step — do not skip)

Profile the raw artifact, then in **two parts** turn what you observe into the contract:

**Part 1 — Structure.** Confirm it parsed correctly (delimiter/encoding/header), is a single
**tidy** table (one variable per column, one value per cell, one observation per row — no merged
cells, stacked sub-tables, or multi-value cells), and that names/dtypes are sane. A mis-parsed
table makes every column check meaningless; structural defects become transforms/checks too.

**Part 2 — Per-column contract + rules + guardrails.** Per column, determine its semantic type
and **canonical form**, then emit: **dtype**, **nullable?**, **key?**, **range** (numeric
min/max), **regex** (format), **canonical categories + a `merge_map`** of variants → canonical
(repair guidance, *not* a check-time substitution), **severity** (default `high` for keys/required
columns, else `normal`), and an optional **outlier method**. Add **cross-column rules** the data
evidences (e.g. `start ≤ end`). Then the guardrails above (`retention_floor`, `protected_columns`,
`impute_cap`). Three rules keep this trustworthy: **commitment** — *every* observed anomaly
compiles to a check or is explicitly waived with a reason (several spellings of a value MUST get a
`categories` check, never stay free text); **canonical form is the stored value** — declaring a
canonical set *creates* the open violations the loop clears by rewriting; **strictness bias** —
when unsure, add the stricter check (over-strictness is cheap to undo; a wrong check is worse than
a missing one, so never guess column meaning the data doesn't evidence).

Confirm the inferred contract with the user (Claude Code: present as a compact table via
`AskUserQuestion`; other: print as YAML and ask to confirm/amend). After sign-off, write the
contract + the **compiled checklist** into `<sandbox_root>/tcl/schema.yaml`; the contract is then
fixed for the run. Full contract shape: `examples/run.example.yaml`.

### The checklist

Each contract rule compiles to one binary check that reports a **violation count** and a state.
There is no weighted float and no epsilon — that single fact removes all denominator ambiguity.

| check id (pattern) | dimension | counts violations where… |
|---|---|---|
| `<col>.required` | completeness | a `nullable:false` cell is null |
| `<col>.type` | validity | a non-null cell isn't parseable as the contract dtype |
| `<col>.range` | validity | a non-null numeric cell is outside `[min,max]` |
| `<col>.regex` | validity | a non-null cell fails the format regex |
| `<col>.categories` | consistency | a non-null **stored** value isn't a canonical category |
| `<rule_id>` (cross-column) | consistency | a row violates a cross-column rule |
| `<col>.key` | uniqueness | a declared-key value is duplicated |
| `rows.unique` | uniqueness | a row is an exact duplicate |
| `<col>.outlier` *(opt-in)* | plausibility | a numeric cell is a statistical outlier (only if a method is declared) |

**Check states:** `pass` (0 violations) · `open` (violations remain, still attackable) ·
`residual` (violations remain but can't be fixed within guardrails without regressing another
check — an accepted, reported dead end). **Nulls are a violation only for `.required`** — the
`.type`/`.range`/`.regex` checks ignore nulls. **Priority** among open checks: highest
`severity` first, then most violations. The **headline** `checks_passing% = checks_in_pass /
total_checks` is for `report.md` and status lines only — it never drives keep/revert.
*Honest limit:* the checklist measures **well-formed & self-consistent**, not true accuracy (is
"John Smith" the *correct* name?) — outlier/range checks are the plausibility proxy.

## The loop

Let `<best>` be the current accepted version (starts at `v0`, an exact copy of `<artifact>`).
Copy this checklist and tick items off, iterating on `<best>` until a stop condition fires:

- [ ] **Profile `<best>`** — run deterministic profiling code → `profiles/profile-vN.json` (schema below): per-column stats + **every check's violation count + state** + `retention` + headline `checks_passing%`; write a 4–8 line human summary.
- [ ] **Pick the target & propose ONE transform** — among `open` checks, pick by priority (severity high, then most violations). State the check id, its violation count, the repair strategy, and the expected effect. Never propose a transform you can't tie to a specific open check.
- [ ] **Write the transform** as a pure `transform(df) -> df` pandas function, deterministic, touching only what the target check requires (it must run standalone in `pipeline.py` later).
- [ ] **Apply → candidate** — load `<best>`, apply, write `versions/vN+1.<ext>`. On error, fix once; if still broken, log `status=crash` and discard (don't advance `<best>`).
- [ ] **Re-profile the candidate** — re-run the checklist on `vN+1` for new violation counts + `retention`.
- [ ] **Keep or revert (pure checklist logic, no epsilon)** — accept iff the **target check's violations strictly decreased** AND **no other check's violations increased** AND **no guardrail tripped**. Else revert. If that was the last guardrail-safe strategy for the target, mark it `residual`.
- [ ] **Log + persist** — append one `ledger.tsv` row. If kept: copy the function to `transforms/tNN_<slug>.py` and append its call to `pipeline.py` in order.
- [ ] **Check stops** — if none fired, go to the next iteration on the new `<best>`.

**Least-destructive principle (the loop's bias):** prefer **repair over removal**. Try, and take
the first that is guardrail-safe and regression-free: (a) **repair** (parse/standardize/
canonicalize the value), (b) **impute** (within `<impute_cap>`, flagged synthetic — nulling an
unrecoverable value in a `nullable:true` column is *repair*, not imputation, and is uncapped),
(c) **remove** (drop rows/cols, within retention + protected floors). Removal is a last resort.
A check becomes `residual` only when **all three** genuinely fail — e.g. a malformed value in a
`nullable:false` column where repair can't recover it, dropping breaches retention, and nulling
would regress that column's `.required` check. An honest residual is correct; never null a
required field or invent a value just to clear a check.

## Stops

Because checks are deterministic counts, "done" is **exact** — no epsilon, no plateau heuristic.
**This is the key difference from the autoresearch loops: it is designed to terminate.** Stop on
**any**:
1. **All green** — every check is `pass`. The clean, successful exit.
2. **All-residual** — zero `open` checks remain (every check is `pass` or `residual`); the
   remaining violations are provably unfixable within the guardrails. The natural exit.
3. **Budget** — `<gate>`/`<budget>` reached. Backstop only.

Before marking the **last** open check `residual` (which triggers stop #2), confirm you actually
tried all three strategies (repair → impute → remove) — don't declare it unfixable just because
the first regressed another check or hit a floor.

**On stop:** set `cleaned.<ext>` to `<best>`, write `report.md`, and print the final summary
(headline `checks_passing%`, pass/residual counts, which stop fired).

## Outputs & formats

The run produces **three deliverables**:
1. **`cleaned.<ext>`** — the best version (copy of `<best>`).
2. **`pipeline.py`** — a standalone, replayable script: read raw `<artifact>` → apply each
   accepted transform in order → write cleaned. Deterministic and idempotent; re-running it on the
   raw dump reproduces `cleaned.<ext>` exactly. The audit-grade artifact.
3. **`ledger.tsv` + `report.md`** — the full audit trail and a before/after summary.

`<sandbox_root>/tcl/` layout: `schema.yaml` (bindings + contract + compiled checklist),
`versions/` (`v0.<ext>` is the READ-ONLY copy of the raw artifact; new `vN` written per
candidate), `transforms/` (one file per accepted transform), `profiles/`, `ledger.tsv`,
`pipeline.py`, `report.md`.

**`ledger.tsv`** — tab-separated, append-only, one row per attempt, never commas in free text.
One row per `schemas/ledger.schema.json`; `status` ∈ {`keep`,`revert`,`residual`,`crash`}:
```
iter	transform_id	target_check	dimension	viol_before	viol_after	regressions	retention	status	rows_affected	cells_affected	summary
1	t01_drop_dupes	rows.unique	uniqueness	7	0	0	1.000	keep	7	0	remove 7 exact duplicate rows
2	t02_canon_status	status.categories	consistency	142	0	0	1.000	keep	0	142	rewrite variants to canonical set
3	-	contact.regex	validity	3	3	-	0.94	residual	-	-	repair impossible; drop breaches retention; null regresses contact.required
```

**`profiles/profile-vN.json`** — per `schemas/profile.schema.json` (per-column stats + every
check's count & state + retention + headline). Compact instance:
```json
{"version":"v2","rows":980,"cols":7,"checks_total":11,"checks_passing":9,
 "checks_passing_pct":0.82,"total_violations":3,"retention":0.98,
 "checks":[{"id":"status.categories","dimension":"consistency","scope":"status",
            "severity":"normal","violations":0,"state":"pass"}],
 "columns":[{"name":"status","dtype":"object","contract_dtype":"category",
             "pct_null":0.0,"n_unique":5}],
 "summary":"status canonicalized; one regex check residual on contact."}
```

**`report.md`** — v0-vs-final headline `checks_passing%`, the full checklist with start/end
violation counts, the confirmed contract, the ordered accepted transforms (the pipeline), the
**residual set** (with why), what was dropped/imputed, and which stop fired.

## Constraints
- **The raw `<artifact>` is never modified** — all work is in `<sandbox_root>/tcl/`; `v0` is a
  copy, and the loop only writes new `vN` versions, because the raw dump is the replay ground truth.
- **Never add rows, fabricate a key/index, or invent values silently** — imputation is allowed but
  flagged synthetic, logged, and capped at `<impute_cap>` per column.
- **Respect the guardrails** — a candidate breaching the retention floor, dropping a protected
  column, or exceeding the impute cap is reverted no matter how many checks it cleared, because a
  checklist is otherwise gameable by deletion.
- **Every check is a deterministic count**, not LLM judgement; the confirmed contract is the sole
  authority for "correct" — do not silently change the contract or compiled checklist mid-run.
- **Keep/revert is pure checklist logic** — keep iff the target check improves with no regression
  and no guardrail breach. No epsilon, no weighted score driving the decision.
- **One transform per iteration**, a pure pandas function tied to one open check, so each
  violation delta is attributable; no blind multi-step rewrites.
- **A check unfixable within the guardrails becomes `residual`** and is reported — never forced
  shut by fabricating or nulling required data.
- **Keep `pipeline.py` faithful** — exactly the accepted transforms in order; re-running it on the
  raw dump must yield `cleaned.<ext>`.
- Do not pause to ask whether to continue while open checks remain — setup is the only human
  checkpoint; the loop runs to a stop condition. Do not install packages the env lacks beyond a
  consented pinned install, and do not commit `tcl/` to git.
