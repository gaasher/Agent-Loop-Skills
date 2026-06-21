---
name: tabularCleanupLoop
description: >
  Use when the user has a messy tabular data dump (CSV/TSV/parquet/Excel) and wants it
  turned into a clean, analysis/ML-ready dataset with no human in the loop. A single agent
  profiles the table, proposes and applies one targeted cleanup transform at a time
  (types, nulls, duplicates, inconsistent categories, format/range violations, outliers),
  scores the result against an intrinsic, label-free data-quality objective, and keeps or
  reverts. It repeats until the data stops improving, all contract checks pass, or a budget
  is hit — logging every transform to an auditable ledger and emitting a replayable cleaning
  pipeline. Runs autonomously until a stop condition fires.
metadata:
  version: "0.1.0"
---

# tabularCleanupLoop

A **single agent** that takes a messy data dump (`<artifact>`) to the cleanest defensible
state, **no human in the loop** once running. Each iteration it **profiles** the table,
**diagnoses** the worst remaining defect, **applies one transform** (as pandas code),
**scores** the result against an intrinsic, label-free **data-quality objective**
(`<objective>`), and **keeps or reverts**. Every accepted transform is appended to a
replayable `pipeline.py`; every attempt is logged to the `ledger`.

This is **analysis-first and label-free**: the score is computed purely from the data
itself (no target column, no downstream model) against a **data contract** the agent
**infers at setup and confirms with you once**, then enforces autonomously. The design is the
Amazon **Deequ** pipeline — *constraint suggestion → metrics computation → constraint
verification* (Schelter et al., VLDB 2018) — expressed as the **DAMA / ISO 25012** quality
dimensions, scored as a Great-Expectations-style weighted success rate, and optimized in a
keep-the-best agent loop bent from *Exploring LLM Agents for Cleaning Tabular ML Datasets*
(Yu et al., 2025, arXiv:2503.06664). Where that paper scores by downstream model F1, this
loop scores by **intrinsic data quality**, so it works on unlabeled / EDA-bound data.

**You are the controller.** Do not pause for permission once the loop is running. The loop
**is designed to terminate** (unlike the autoresearch loops): it runs until a stop condition
in §3 fires — not forever.

Files (all in this folder):
- `schemas/schema.example.yaml` — the resolved bindings written to `<sandbox_root>/tcl/schema.yaml`.
- `schemas/profile.schema.json` — the per-iteration data-quality profile report.
- `schemas/ledger.schema.json` — one ledger row per attempted transform.

---

## The objective in one paragraph (read this first)

The **contract is a checklist** (per column: type, nullable?, valid range / allowed set,
format regex, canonical categories, which columns are keys; plus a few cross-column rules).
**Each rule yields a pass rate in `[0,1]`** — `passing_cells / total_cells` (e.g. "92% of
`age` in [0,120]"). Rules are grouped into **five label-free dimensions**; average within a
dimension, then take a **weighted average across dimensions → one number, the composite**.
A transform is "good" **iff it raises the composite** by more than `<epsilon>`. The composite
is **gameable** (drop every bad row → "100% valid" but data destroyed), so an improvement
only counts if the **retention floor** holds (§1e). That single guard makes a label-free
score safe to optimize blindly. *Honest limit:* intrinsic scoring measures **well-formed &
self-consistent** (validity, consistency, completeness, uniqueness, plausibility); it cannot
measure true **accuracy** (is "John Smith" the *correct* name?) — that needs ground truth we
don't have. Plausibility is the proxy.

| dimension | weight | check (pass rate in [0,1]) |
|-----------|--------|----------------------------|
| completeness | 0.25 | non-null rate on columns the contract marks required |
| validity | 0.25 | cells parseable as the contract dtype **and** passing range/regex |
| consistency | 0.20 | categorical values mapping to a canonical category + cross-column rules |
| uniqueness | 0.15 | `1 − duplicate_rows/rows`; declared keys are unique |
| plausibility | 0.15 | numeric cells within plausible (non-outlier) bounds |

`composite = Σ weightᵢ · scoreᵢ`. Every sub-score is computed by **deterministic code**, never
LLM judgement.

**Null handling (avoid double-counting).** A null cell is scored **only** by *completeness*.
Exclude nulls from the denominators of *validity*, *consistency*, and *plausibility* — i.e.
those are `passing / non_null_cells`, not `passing / total_cells`. A legitimately-null value
in a `nullable: true` column must NOT count as a validity/plausibility failure (otherwise
"fix the bad values" can never reach 1.0 and the loop chases an unreachable score). Nulls in a
`nullable: false` column are penalized by completeness, which is the single place they count.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question below and wait for the user's explicit
answer — do NOT infer or skip any.** Setup is the ONLY place the human is in the loop; once
you start §2 you run autonomously.

### 1.0 Detect host
`AskUserQuestion` available → **`<host>`** = `claude-code` or `other`. On Claude Code,
infer a recommended answer for each question and confirm via `AskUserQuestion`; otherwise
ask each as a quoted prompt and wait for a typed reply.

### 1a. The artifact — the data dump to clean
**`<artifact>`** — path to the messy table. Detect the format from the extension
(`.csv/.tsv/.parquet/.xlsx/.json`); record **`<format>`** and the read/write calls to use
(e.g. `pd.read_csv` / `pd.read_parquet`). **The raw artifact is READ-ONLY and never
mutated** — `v0` is a copy of it (§1g). For delimited files, also detect and record the
**delimiter, encoding, header row, and quote char** now (sniff with `pandas`/`csv`), since a
mis-parsed dump is the most common first defect.

### 1b. Sandbox location
**`<sandbox_root>`** — where `tcl/` (versions, transforms, ledger, pipeline) is created.
Default: `./sandbox` next to the artifact.

### 1c. The data-quality objective — defaults or customize
The objective is the weighted composite of the five dimensions above. Ask one yes/no:
**"Use the default quality objective (weights shown above), or customize the weights?"**
- **Defaults (recommended)** → use the table above; ask nothing more.
- **Customize** → ask only for the weights the user wants to change (they must still sum to
  1.0). Optionally allow weighting **key/critical columns** higher within a dimension.

### 1d. The data contract — INFER, then CONFIRM (the only content decision the human makes)
Before the loop, **profile the raw artifact once** (Deequ "constraint suggestion") and
**propose a contract**, then show it to the user for approval. The contract is the spec of
"correct" the objective scores against — per column: intended **dtype**, **nullable?**,
**value range / allowed set**, **format/regex**, **canonical categories** (with a merge map
for obvious variants, e.g. `{USA, U.S.A., us} → "US"`), declared **keys** (unique columns),
and any **cross-column rules** the data implies (e.g. `start_date ≤ end_date`).
- **Claude Code**: present the inferred contract as a compact table via `AskUserQuestion`
  ("Approve this contract / I'll edit it"); accept edits, then lock it.
- **Other**: print the contract as YAML and ask the user to confirm or amend.

Record as **`<contract>`** → written into `schema.yaml`. After this, **no more questions** —
the contract is the agent's sole authority for what "correct" means for the rest of the run.

### 1e. Guardrails — anti-gaming floors (defaults or customize)
The composite is **gameable** (drop every row with a null → completeness = 1.0 but the data
is destroyed). These hard floors make it safe; a candidate that trips any is **reverted
regardless of its score**:
- **`<retention_floor>`** (default `0.95`) — cumulative `unique_informative_rows_kept /
  rows_in_v0` must stay ≥ this. (Exact-duplicate removal is retention-neutral — duplicates
  are not informative — so dedup is "free".)
- **`<protected_columns>`** (default: all columns) — columns that must survive; dropping one
  requires the user to have allowed it here.
- **`<impute_cap>`** (default `0.20`) — max fraction of a column's cells that may be imputed.
- **Never** add rows, fabricate a key/index, or edit the raw artifact. Imputation is allowed
  but **flagged synthetic, logged, and capped** by `<impute_cap>`.
Ask only if the user opted to customize; else use defaults.

### 1f. Budget and convergence
- **`<gate>`** = `iterations` (default) | `tokens` | `time`, and **`<budget>`** = the cap
  (default: `30` iterations / `500k` tokens / `30` minutes).
- **`<target_composite>`** (default `0.99`) — the "all green" success threshold.
- **`<epsilon>`** (default `0.005`) — minimum composite gain to count as improvement.
- **`<plateau_K>`** (default `3`) — consecutive non-improving iterations that trigger a
  plateau stop.

### 1g. Initialise sandbox
```
<sandbox_root>/tcl/
├── schema.yaml          ← resolved bindings + the confirmed contract (written now)
├── versions/
│   └── v0.<ext>         ← exact copy of <artifact> (READ-ONLY baseline)
├── transforms/          ← one pandas function file per ACCEPTED transform (created as kept)
├── profiles/            ← profile-<vN>.json per scored version (schemas/profile.schema.json)
├── ledger.tsv           ← append-only, every attempt (header only now)
├── pipeline.py          ← replayable cleaning script (raw → cleaned); stub now
└── report.md            ← final before/after summary (written at the end)
```
**`ledger.tsv` header** (tab-separated): `iter	transform_id	dimension	quality_before	quality_after	delta	retention	status	rows_affected	cells_affected	summary`
Write all resolved bindings + `<contract>` to `schema.yaml`. **Copy** (never symlink) the raw
artifact to `versions/v0.<ext>`.

### 1h. Confirm and go
Print the resolved bindings, the confirmed contract, the v0 baseline composite + every
sub-score, and the derived budget. **Do not start the loop until the user confirms.** Once
confirmed, run §2 autonomously to a stop condition.

---

## 2. The cleanup loop

Let **`<best>`** be the highest-composite version so far (starts at `v0`). Each iteration
operates on `<best>` and produces a candidate `vN+1`.

**Least-destructive principle (the loop's bias):** prefer **repair over removal**. A
transform that *parses / standardizes / imputes* a value is better than one that *drops* a
row or column. When two transforms gain similar quality, pick the one that loses less
information. Dropping is a last resort, only for genuinely unsalvageable data, and always
within the retention floor.

**Irreconcilable defects (don't force a fix).** Some defects cannot be repaired without
fabricating data — e.g. a cross-column violation where both values are plausible and neither
is clearly wrong (`signup_date > last_seen_date`), or a malformed value in a `nullable: false`
column. Dropping the row may breach retention; nulling a required column trades a consistency
gain for a completeness loss and usually fails the keep test. When neither a guardrail-safe
repair nor a guardrail-safe removal improves the composite, **leave the defect in place and
record it in `report.md`** as a known residual. Do not null a required field or fabricate a
value to make the score move — an honest residual is correct behavior, not a failure.

### LOOP until a stop condition (§3) fires:

**1. Profile `<best>`.** Run deterministic profiling code → write
`profiles/profile-vN.json` (`schemas/profile.schema.json`): per-column dtype vs contract,
%null, cardinality, top categorical values + suspected variant clusters, duplicate-row
count, constraint violations (which rule, how many), outlier counts, and every dimension
sub-score + the composite + retention. Also write a 4–8 line human summary.

**2. Diagnose & propose ONE transform.** Rank issues by **impact** = (sub-score deficit ×
cells affected), filtered by what the contract says is wrong. Pick the single worst
*defensible* issue. State, grounded in the profile (cite the column + the stat, like an
empirical anchor):
- the defect (column + number/pattern from `profile-vN.json`),
- the transform (the exact repair),
- which dimension it should raise and the predicted direction,
- the expected retention impact.
Do **not** propose a transform you can't anchor to a profile number.

**3. Write the transform as a pure function.** A function `transform(df) -> df` in pandas,
deterministic, idempotent where possible, touching only what the defect requires. Keep it
self-contained (it must run standalone in `pipeline.py` later).

**4. Apply → candidate.** Load `<best>`, apply the function, write `versions/vN+1.<ext>`.
If the function errors, fix it once (trivial bug); if still broken, log `status=crash` and
discard the candidate (do not advance `<best>`).

**5. Score the candidate.** Profile `vN+1` exactly as step 1 → composite + retention.

**6. Keep or revert.** Accept `vN+1` as the new `<best>` iff **all** hold:
   - `composite(vN+1) − composite(<best>) > <epsilon>`, AND
   - no guardrail (§1e) tripped, AND
   - `retention(vN+1) ≥ <retention_floor>`.
   Otherwise revert (`<best>` unchanged).
   *Simplicity exception:* if the composite is within ε but the candidate is meaningfully
   cleaner structurally (junk columns removed, simpler types, canonical values, normalized
   formats) at no retention cost, keep it. A simplicity-exception keep **is** an accepted
   transform — log it `keep` and **reset the plateau counter** (§3). These transforms are
   one-time and idempotent, so they cannot churn forever.

**7. Log + persist.** Append one `ledger.tsv` row (status ∈ {`keep`,`revert`,`crash`}). If
kept: copy the function to `transforms/tNN_<slug>.py` and **append its call to `pipeline.py`**
in order.

**8. Check stop conditions (§3).** If none fired, go to step 1 on the new `<best>`.

---

## 3. Stop conditions (the loop ENDS — the key difference from the autoresearch loops)

Stop when **any** of these fires:
1. **All checks green** — every hard contract rule passes AND `composite ≥ <target_composite>`.
   The clean, successful exit.
2. **Plateau** — `<plateau_K>` consecutive iterations with no accepted transform (no defect
   yields a > ε, guardrail-safe gain). The natural "data stopped improving" exit.
3. **Budget** — `<gate>`/`<budget>` reached (iterations, tokens, or wall-clock). Backstop.
4. **No defensible proposal** — step 2 can find no contract-grounded issue left to fix.

**Anti-premature-stop guard:** on a plateau where checks are NOT all green, before concluding
you MUST try a **different quality dimension** than the ones that just failed — re-profile for
a defect type you haven't addressed (categorical variants, cross-column rules, outliers,
type validity). Only declare plateau after a different dimension also yields nothing. (Don't
quit while defensible defects remain.)

**On stop:** set `cleaned.<ext>` to `<best>`, then write `report.md` (§4) and print the final
summary. Do not commit `tcl/` to git; leave it untracked.

---

## 4. Outputs & formats

The run produces **three deliverables**, not just a clean file:
1. **`cleaned.<ext>`** — the best version (copy of `<best>`).
2. **`pipeline.py`** — a standalone, replayable script: `read raw <artifact> → apply each
   accepted transform in order → write cleaned`. Deterministic and idempotent; re-running it
   on the raw dump reproduces `cleaned.<ext>` exactly. This is the audit-grade artifact.
3. **`ledger.tsv` + `report.md`** — the full audit trail and a before/after summary.

**`ledger.tsv`** (every attempt, append-only):
```
iter	transform_id	dimension	quality_before	quality_after	delta	retention	status	rows_affected	cells_affected	summary
1	t01_strip_whitespace	validity	0.612	0.658	0.046	1.000	keep	0	1840	trim + casefold object cols
2	t02_drop_dupes	uniqueness	0.658	0.690	0.032	1.000	keep	312	0	remove 312 exact duplicate rows
3	-	completeness	0.690	0.690	0.000	0.41	revert	-	-	dropping null rows breaches retention floor
```
**`profiles/profile-vN.json`** — see `schemas/profile.schema.json` (per-column stats + all
sub-scores + composite + retention).

**`report.md`** — v0-vs-final composite and every sub-score, the confirmed contract, the
ordered list of accepted transforms (the pipeline), what was dropped/imputed and why, and
which stop condition fired.

---

## 5. Hard constraints (never violate)
- **The raw `<artifact>` is never modified.** All work happens in `<sandbox_root>/tcl/`.
  `v0` is a copy; the loop only ever writes new `vN` versions.
- **Never add rows, fabricate a key/index, or invent values silently.** Imputation is allowed
  but flagged synthetic, logged, and capped at `<impute_cap>` per column.
- **Respect the guardrails (§1e):** a candidate breaching the retention floor, dropping a
  protected column, or exceeding the impute cap is reverted no matter how high its score.
- **Every sub-score is computed by deterministic code**, not LLM judgement. The contract
  (§1d) is the sole authority for "correct"; do not silently change it mid-run.
- **One transform per iteration**, written as a pure pandas function, anchored to a profile
  number. No blind multi-step rewrites.
- **Keep `pipeline.py` faithful:** it contains exactly the accepted transforms, in order, and
  re-running it on the raw dump must yield `cleaned.<ext>`.
- **The loop terminates** on a §3 stop condition — but do **not** pause to ask the human
  whether to continue while defensible defects remain. Setup is the only human checkpoint.
- Do not install packages beyond what's already available; do not commit `tcl/` to git.
