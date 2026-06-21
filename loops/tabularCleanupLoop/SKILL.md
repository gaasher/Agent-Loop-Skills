---
name: tabularCleanupLoop
description: >
  Use when the user has a messy tabular data dump (CSV/TSV/parquet/Excel) and wants it
  turned into a clean, analysis/ML-ready dataset with no human in the loop. A single agent
  profiles the table, compiles an inferred data contract into a checklist of deterministic
  pass/fail checks, then applies one targeted transform at a time (types, nulls, duplicates,
  inconsistent categories, format/range violations, outliers) to resolve checks, keeping a
  transform only if it reduces its target check's violations without regressing another check
  or breaching a guardrail. It repeats until every check passes, every remaining check is an
  unfixable residual, or a budget is hit — logging every attempt to an auditable ledger and
  emitting a replayable cleaning pipeline. Runs autonomously until a stop condition fires.
metadata:
  version: "0.2.0"
---

# tabularCleanupLoop

A **single agent** that takes a messy data dump (`<artifact>`) to the cleanest defensible
state, **no human in the loop** once running. The agent compiles the data contract into a
**checklist of deterministic pass/fail checks**, then each iteration **profiles** the table
(runs the checklist), **picks the worst open check**, **applies one transform** (as pandas
code) to resolve it, and **keeps or reverts** based on whether that check improved with no
collateral damage. Every accepted transform is appended to a replayable `pipeline.py`; every
attempt is logged to the `ledger`.

**The recipe is a decomposition, not a one-shot clean:** **(1) structure** — get the table
well-formed (parse correctly, one tidy table, sane types); **(2) contract synthesis** — turn
the dataset's *observed* issues into an explicit checklist where **every anomaly becomes a
check**; **(3) the fix loop** — resolve checks one transform at a time (§2). **Stage 2 is where
quality is won or lost:** an issue the profiler notices but never compiles into a check (the
classic being many spellings of one category) silently survives into the output — a green
checklist over dirty data. "Understand the dataset" as prose is worthless; *committing every
observation to a check* is the point.

This is **analysis-first and label-free**: checks are computed purely from the data itself (no
target column, no downstream model) against a **data contract** the agent **infers at setup
and confirms with you once**, then enforces autonomously. The design is the Amazon **Deequ**
pipeline — *constraint suggestion → metrics computation → constraint verification* (Schelter et
al., VLDB 2018): the contract is a set of **Great-Expectations-style binary checks** ("88% in
range" is just `count of violating cells`), grouped into the **DAMA / ISO 25012** dimensions
for reporting. The loop is bent from *Exploring LLM Agents for Cleaning Tabular ML Datasets*
(Yu et al., 2025, arXiv:2503.06664), but where that paper scores by downstream model F1, this
loop drives off the **checklist**, so it works on unlabeled / EDA-bound data.

**You are the controller.** Do not pause for permission once the loop is running. The loop
**is designed to terminate** (unlike the autoresearch loops): it runs until a stop condition
in §3 fires — not forever.

Files (all in this folder):
- `schemas/schema.example.yaml` — the resolved bindings written to `<sandbox_root>/tcl/schema.yaml`.
- `schemas/profile.schema.json` — the per-iteration checklist profile report.
- `schemas/ledger.schema.json` — one ledger row per attempted transform.

---

## The objective: a checklist, not a score (read this first)

The contract **compiles to a checklist of deterministic checks**. Each check is binary at the
cell/row level and reports a **violation count** — there is no weighted float, no epsilon, no
"how good is this number". A check is one of:

| check id (pattern) | dimension | counts violations where… |
|--------------------|-----------|--------------------------|
| `<col>.required` | completeness | a `nullable:false` cell is null |
| `<col>.type` | validity | a non-null cell isn't parseable as the contract dtype |
| `<col>.range` | validity | a non-null numeric cell is outside `[min,max]` |
| `<col>.regex` | validity | a non-null cell fails the format regex |
| `<col>.categories` | consistency | a non-null **stored** value isn't one of the allowed canonical categories |
| `<rule_id>` (cross-column) | consistency | a row violates a cross-column rule (e.g. `start ≤ end`) |
| `<col>.key` | uniqueness | a declared-key value is duplicated |
| `rows.unique` | uniqueness | a row is an exact duplicate |
| `<col>.outlier` *(opt-in)* | plausibility | a numeric cell is a statistical outlier (only if the contract declares a method) |

(These ids are a *pattern* — `<col>` is each real column — not a fixed list; the contract
determines which checks exist.)

**Checks read the *stored* value — normalization is real work, not a check-time trick.** A
check never silently "fixes" a value before judging it. `<col>.categories` compares the value
*as stored* against the canonical set, so a non-canonical-but-recognizable value (`"usa"` when
the canonical is `"US"`) is an **open violation**, not a pass. A `merge_map` is **repair
guidance** for the transform that clears it, never a transformation applied at check time. This
is the difference between a checklist that turns green and a dataset that is actually clean:
the loop only goes green once the stored values are canonical, so `cleaned.<ext>` really
contains the normalized data.

**Check states:** `pass` (0 violations) · `open` (violations remain and it's still attackable)
· `residual` (violations remain but *cannot* be fixed within the guardrails without regressing
another check — an accepted, reported dead end). **Nulls are a violation only for
`.required` checks** (a legitimate null in a `nullable:true` column is not a `.type`/`.range`/
`.regex` violation — those checks ignore nulls). That single rule removes all the
denominator/double-counting ambiguity a fractional score would have.

**Priority** when several checks are open: highest **severity** first (keys and required
fields default to `severity: high`), then **most violations**. Severity is the only knob, and
it replaces dimension weights — it expresses "a duplicated primary key matters more than 100
inconsistent capitalizations" directly, instead of via a tuned average.

**Headline number (reporting only, never drives control flow):**
`checks_passing% = checks_in_pass / total_checks`. Use it in `report.md` and status lines so a
human gets a one-glance read; the loop itself only ever asks "did the target check's violation
count go down without breaking another check?".

*Honest limit:* the checklist measures **well-formed & self-consistent** (validity,
consistency, completeness, uniqueness, plausibility). It cannot measure true **accuracy** (is
"John Smith" the *correct* name?) — that needs ground truth we don't have. Outlier/range
checks are the plausibility proxy.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question below and wait for the user's explicit
answer — do NOT infer or skip any.** Setup is the ONLY place the human is in the loop; once
you start §2 you run autonomously. *(A non-interactive caller — e.g. a test harness — may
instead supply all bindings up front and skip the questions; the loop body §2–§5 is
unchanged.)*

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

### 1c. Understand → contract (the decomposition that matters — do NOT skip)
A column staying dirty while the checklist reads "green" comes from a weak contract, so this is
where the real work is. Two parts; **profiling that doesn't end in a check changes nothing.**

**Part 1 — Structure.** Get the table well-formed *before* reasoning about columns: confirm it
parsed correctly (delimiter/encoding/header row), that it is a single **tidy** table (one
variable per column, one value per cell, one observation per row — no merged cells, stacked
sub-tables, or multi-value cells), and that column names/dtypes are sane. A mis-parsed table
makes every column-level check meaningless; structural defects become transforms/checks too.

**Part 2 — Contract synthesis (infer → confirm).** Profile the raw artifact (Deequ "constraint
suggestion") and, **per column**, determine its *semantic type* (id, email, currency, date,
category, free-text, numeric-measure…) and its **canonical form**, then emit the contract:
**dtype**, **nullable?**, **range / allowed set**, **format/regex**, **canonical categories**
(the allowed values), declared **keys**, **severity** (default `high` for keys and required
columns, else `normal`), optional **outlier method**, and **cross-column rules** the data
evidences. Three rules make this stage trustworthy — they are the fix for the green-but-dirty
failure mode:
- **Commitment.** *Every* anomaly profiling surfaces MUST compile to a check (or be explicitly
  waived in the contract with a stated reason). A column with several spellings of a few values
  MUST get a `categories` check with the canonical set + a `merge_map` of variants → canonical —
  **never** left as free text. An observed-but-unenforced issue is exactly how a column stays
  dirty while the checklist reads "green".
- **Canonical form is the stored value.** Checks judge the value *as stored* (see the objective
  section), so declaring a canonical set *creates* the open `categories` violations the loop
  must clear by rewriting variants — which is what actually cleans the column.
- **Strictness bias.** When unsure whether to add a check or how canonical to be, **add the
  stricter check**: a lenient contract that lets a dirty table go "all green" fast is the primary
  failure mode, and over-strictness is cheap to undo (the human confirms below; genuinely
  unfixable checks become `residual`). Do **not** infer the dataset's business *purpose* or
  invent column meanings the data doesn't evidence — an unknown column stays loose (fewer
  checks), never guessed. A wrong check is worse than a missing one.

Confirm with the human (the only content decision they make):
- **Claude Code**: present the inferred contract as a compact table via `AskUserQuestion`
  ("Approve / I'll edit"); accept edits, then lock it.
- **Other**: print the contract as YAML and ask the user to confirm or amend.

Record as **`<contract>`** → written into `schema.yaml`; the agent then **compiles it into the
explicit checklist** (recorded too), fixed for the run. After confirmation, **no more
questions** — the contract is the sole authority for what "correct" means.

### 1d. Guardrails — anti-gaming floors (defaults or customize)
A checklist is gameable by deletion (drop every row with a bad value → that check passes, but
the data is destroyed). These hard floors make it safe; a candidate that trips any is
**reverted regardless of how many violations it cleared**:
- **`<retention_floor>`** (default `0.95`) — cumulative `unique_rows_kept / unique_rows_in_v0`
  must stay ≥ this. The denominator is v0's **deduplicated** row count, so removing exact
  duplicates is retention-neutral (it lowers neither numerator nor denominator).
- **`<protected_columns>`** (default: all columns) — columns that must survive; dropping one
  requires the user to have allowed it here.
- **`<impute_cap>`** (default `0.20`) — max fraction of a column's cells that may be **imputed**,
  where imputation means inserting a *substitute/estimated* value (mean, mode, forward-fill, a
  constant). Nulling an unrecoverable value in a `nullable:true` column is **repair, not
  imputation** (nothing synthetic is inserted) and does not count against this cap.
- **Never** add rows, fabricate a key/index, or edit the raw artifact. Imputation is allowed
  but **flagged synthetic, logged, and capped** by `<impute_cap>`.
Ask only if the user opted to customize; else use defaults.

### 1e. Budget
- **`<gate>`** = `iterations` (default) | `tokens` | `time`, and **`<budget>`** = the cap
  (default: `30` iterations / `500k` tokens / `30` minutes). This is a **backstop only** — the
  loop normally stops on its own when the checklist is all-pass-or-residual (§3). There is no
  epsilon and no plateau counter: checks are deterministic, so "done" is exact.

### 1f. Initialise sandbox
```
<sandbox_root>/tcl/
├── schema.yaml          ← resolved bindings + the confirmed contract + compiled checklist (now)
├── versions/
│   └── v0.<ext>         ← exact copy of <artifact> (READ-ONLY baseline)
├── transforms/          ← one pandas function file per ACCEPTED transform (created as kept)
├── profiles/            ← profile-<vN>.json per scored version (schemas/profile.schema.json)
├── ledger.tsv           ← append-only, every attempt (header only now)
├── pipeline.py          ← replayable cleaning script (raw → cleaned); stub now
└── report.md            ← final before/after summary (written at the end)
```
**`ledger.tsv` header** (tab-separated): `iter	transform_id	target_check	dimension	viol_before	viol_after	regressions	retention	status	rows_affected	cells_affected	summary`
Write all resolved bindings + `<contract>` + the compiled checklist to `schema.yaml`.
**Copy** (never symlink) the raw artifact to `versions/v0.<ext>`.

### 1g. Confirm and go
Print the resolved bindings, the confirmed contract, the compiled checklist with v0 violation
counts (and the headline `checks_passing%`), and the budget backstop. **Do not start the loop
until the user confirms.** Once confirmed, run §2 autonomously to a stop condition.

---

## 2. The cleanup loop

Let **`<best>`** be the current accepted version (starts at `v0`). Each iteration operates on
`<best>` and produces a candidate `vN+1`.

**Least-destructive principle (the loop's bias):** prefer **repair over removal**. To resolve a
check, try strategies in this order and take the first that is guardrail-safe and regression-
free: (a) **repair** (parse/standardize/canonicalize the value), (b) **impute** (within
`<impute_cap>`, flagged synthetic), (c) **remove** (drop rows/cols, within retention +
protected-column floors). Removal is a last resort, only for genuinely unsalvageable data.

**Irreconcilable defects → residual (don't force a fix).** A check becomes residual only when
**all three** strategies genuinely fail. The classic case: a malformed value in a
`nullable:false` column where repair can't recover the true value, dropping the row would
breach retention, and nulling would regress that column's `.required` check. *A defect is not
automatically residual:* e.g. a cross-column `start > end` violation is clearable by dropping
the few offending rows **if** that stays within the retention floor — it's residual only if it
doesn't. When no guardrail-safe, regression-free strategy exists, **mark the check `residual`**,
record why, and stop targeting it. An honest residual is correct — never null a required field
or invent a value just to clear a check.

### LOOP until a stop condition (§3) fires:

**1. Profile `<best>` (run the checklist).** Run deterministic profiling code → write
`profiles/profile-vN.json` (`schemas/profile.schema.json`): per-column dtype vs contract,
%null, cardinality, top categorical values + suspected variant clusters, and **every check's
violation count + state** (pass/open/residual), plus `retention` and the headline
`checks_passing%`. Also write a 4–8 line human summary.

**2. Pick the target check & propose ONE transform.** Among `open` checks, pick the target by
**priority** (severity `high` first, then most violations). State, grounded in the profile:
- the target check id + its violation count from `profile-vN.json`,
- the repair strategy (a/b/c) and the exact transform,
- the expected effect (target violations → lower) and any retention cost.
Do **not** propose a transform you can't tie to a specific open check.

**3. Write the transform as a pure function.** A function `transform(df) -> df` in pandas,
deterministic, idempotent where possible, touching only what the target check requires. Keep
it self-contained (it must run standalone in `pipeline.py` later).

**4. Apply → candidate.** Load `<best>`, apply the function, write `versions/vN+1.<ext>`.
If the function errors, fix it once (trivial bug); if still broken, log `status=crash` and
discard the candidate (do not advance `<best>`).

**5. Re-run the checklist on the candidate.** Profile `vN+1` exactly as step 1 → every check's
new violation count + `retention`.

**6. Keep or revert (pure checklist logic — no epsilon).** Accept `vN+1` as the new `<best>`
iff **all** hold:
   - the **target check's violations strictly decreased**, AND
   - **no other check's violations increased** (no regression), AND
   - **no guardrail (§1d) tripped** (`retention ≥ floor`, protected columns intact, impute
     within cap).
   Otherwise **revert** (`<best>` unchanged). If this was the last guardrail-safe strategy for
   the target and none worked, **mark the target `residual`** (§2 above).
   (Normalization — canonicalizing categories, ISO-formatting dates, stripping whitespace — is
   **not** a special case needing an exception: each targets a real open check
   (`<col>.categories`, `<col>.type`), because checks read the *stored* value, so a
   non-canonical value is an ordinary violation the transform clears.)

**7. Log + persist.** Append one `ledger.tsv` row (status ∈ {`keep`,`revert`,`residual`,
`crash`}). If kept: copy the function to `transforms/tNN_<slug>.py` and **append its call to
`pipeline.py`** in order.

**8. Check stop conditions (§3).** If none fired, go to step 1 on the new `<best>`.

---

## 3. Stop conditions (the loop ENDS — the key difference from the autoresearch loops)

Because checks are deterministic counts, "done" is **exact** — no epsilon, no plateau heuristic.
Stop when **any** of these fires:
1. **All green** — every check is in state `pass`. The clean, successful exit.
2. **All-residual** — every check is `pass` or `residual`; i.e. zero `open` checks remain. The
   remaining violations are provably unfixable within the guardrails. The natural exit.
3. **Budget** — `<gate>`/`<budget>` reached (iterations, tokens, or wall-clock). Backstop only.

**Before marking the last open check residual** (which would trigger stop #2), make sure you
actually tried all three strategies (repair → impute → remove) for it — don't declare a check
unfixable just because the first strategy regressed another check or hit a floor. Stop #2 is
correct only once every open check has genuinely exhausted guardrail-safe options.

**On stop:** set `cleaned.<ext>` to `<best>`, then write `report.md` (§4) and print the final
summary (headline `checks_passing%`, pass/residual counts, which stop condition fired). Do not
commit `tcl/` to git; leave it untracked.

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
iter	transform_id	target_check	dimension	viol_before	viol_after	regressions	retention	status	rows_affected	cells_affected	summary
1	t01_drop_dupes	rows.unique	uniqueness	7	0	0	1.000	keep	7	0	remove 7 exact duplicate rows
2	t02_canonicalize_status	status.categories	consistency	142	0	0	1.000	keep	0	142	rewrite variant labels to the canonical set
3	-	contact.regex	validity	3	3	-	0.94	residual	-	-	repair impossible; drop breaches retention; null regresses contact.required
```
**`profiles/profile-vN.json`** — see `schemas/profile.schema.json` (per-column stats + every
check's violation count & state + retention + headline `checks_passing%`).

**`report.md`** — v0-vs-final headline `checks_passing%`, the full checklist with start/end
violation counts per check, the confirmed contract, the ordered list of accepted transforms
(the pipeline), the **residual set** (checks left unfixable, with why), what was dropped/imputed,
and which stop condition fired.

---

## 5. Hard constraints (never violate)
- **The raw `<artifact>` is never modified.** All work happens in `<sandbox_root>/tcl/`.
  `v0` is a copy; the loop only ever writes new `vN` versions.
- **Never add rows, fabricate a key/index, or invent values silently.** Imputation is allowed
  but flagged synthetic, logged, and capped at `<impute_cap>` per column.
- **Respect the guardrails (§1d):** a candidate breaching the retention floor, dropping a
  protected column, or exceeding the impute cap is reverted no matter how many checks it cleared.
- **Every check is a deterministic count**, not LLM judgement. The contract (§1c) is the sole
  authority for "correct"; do not silently change the contract or the compiled checklist mid-run.
- **Keep/revert is pure checklist logic:** keep iff the target check improves with no regression
  and no guardrail breach. No epsilon, no weighted score driving the decision.
- **One transform per iteration**, written as a pure pandas function, tied to one open check.
  No blind multi-step rewrites.
- **A check that can't be cleared within the guardrails becomes `residual`** and is reported —
  never forced shut by fabricating or nulling required data.
- **Keep `pipeline.py` faithful:** it contains exactly the accepted transforms, in order, and
  re-running it on the raw dump must yield `cleaned.<ext>`.
- **The loop terminates** on a §3 stop condition — but do **not** pause to ask the human
  whether to continue while open checks remain. Setup is the only human checkpoint.
- Do not install packages beyond what's already available; do not commit `tcl/` to git.
