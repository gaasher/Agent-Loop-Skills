---
name: ml-autoresearch
description: >
  Use when the user wants an autonomous ML research loop that does more than blindly try changes.
  After every training run the agent analyses what actually happened inside the model — gradients,
  activations, embeddings, errors, data — and grounds the next change in that evidence. A `<literature>`
  on/off dial adds scientific-literature grounding: off behaves as a pure analysis-first loop; on
  searches papers, grades the evidence, and implements only what prior work supports. One change per
  run; loops forever until interrupted. Not for one-off training runs or hyperparameter sweeps.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# ML Autoresearch Loop

This loop is **analysis-first**: every experiment is followed by a diagnostic pass that examines what
happened inside the model, and the next change is a hypothesis grounded in that evidence — not a guess.
The feedback signal is `<metric>` read from the run log; the analysis is the spine that decides what to
change. A `<literature>` dial (`on`/`off`) optionally grounds each change in prior work via the sibling
`literature-search` skill. One change per iteration, so each metric move is attributable.

You are the researcher. Do not pause to ask for permission once the loop is running.

## When to use
Use for an open-ended, autonomous ML research campaign where you want each change motivated by analysis
of the model's actual behaviour. Set `<literature> = off` for a self-contained analysis-and-score loop;
set `<literature> = on` to additionally ground changes in the scientific literature (paper search,
evidence grading, a reusable findings backlog). Not for a single training run, a fixed sweep, or tasks
with no measurable scalar metric. Default to `off` unless the user wants literature grounding or the
problem is a known, well-published one where prior recipes will pay off.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it and skip to
the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available — record `<host>` =
`claude-code`) infer a likely value for each binding from the project and present it as the recommended
option; on other hosts (`<host>` = `other`) ask each as a quoted plain-text prompt. Then write
`loop.run.yaml` (format: `examples/run.example.yaml`) and **confirm every value with the user before
creating any other files.** For `branches` strategy, create `git checkout -b autoresearch/<run_tag>`
(tag from today's date; branch must not exist). For `time` gating, write `<sandbox_root>/run_with_timeout.sh`
(`timeout $(( <budget> * 60 )) <entrypoint> "$@"`) and use it as the run command, hard-killing at
`2 × <budget>` min; for `epochs`, patch the epoch cap in an `<editable_files>` file.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<metric>` / `<metric_direction>` | scalar to optimize + `minimize`/`maximize` | — | scan editable files + README for metric names |
| `<run_cmd>` / `<entrypoint>` | command that runs one experiment end to end | — | `pyproject.toml` / `.venv` / README |
| `<editable_files>` | files fair game to edit (never the eval harness) | — | model / config / train scripts; exclude data, logs, env, harness |
| `<sandbox_root>` | where snapshots + ledgers live | `./sandbox` | next to the editable files |
| `<iter_strategy>` | `snapshots` or `branches` | `snapshots` | is the working dir a clean git repo? |
| `<gate>` / `<budget>` | `time` (min) or `epochs`, and the limit | — | existing time/epoch settings in config |
| `<literature>` | `on` = literature-grounded; `off` = analysis-only | `off` | does the user want paper grounding? |
| `<research_scale>` *(on only)* | depth dial `low`/`medium`/`high`/`x-high` | `medium` | see roles/research-subagent.md |
| `<domain>` *(on only)* | one-phrase problem domain; seeds query phrasing only, never filters | — | infer from data/model/task |
| `<lit_skill_dir>` *(on only)* | install dir of the `literature-search` skill | sibling of this loop | `~/.claude/skills/literature-search/` (adjust per host) |
| `<lit_py>` *(on only)* | Python ≥3.9 interpreter for the lit helper (stdlib-only) | `python3` | independent of `<run_cmd>` |

**FILE EDIT GUARD**: before touching any file at any point — setup or loop — confirm it is in
`<editable_files>`, because everything else is read-only ground truth (the eval harness defines
`<metric>`). No exceptions.

### Literature toolchain (only when `<literature> = on`)
Paper search goes through the sibling **`literature-search` skill** (stdlib-only, no installs):
`<lit> = <lit_skill_dir>/tools/lit_search.py` (note the `tools/` segment). Reuse one cache by
appending `--cache-dir <sandbox_root>/literature/.cache` after the subcommand. Subcommands print JSON;
on failure they print `{"error","fallback"}` and exit non-zero — then **degrade to the host's
WebSearch/WebFetch** (never fabricate citations). Smoke-test `<lit> --help` at setup; if the skill is
absent, tell the user and offer to install it (`cp -r <repo>/loops/literature-search ~/.claude/skills/`)
or proceed degraded. For onboarding and API keys (all optional; a free `S2_API_KEY` is recommended),
run `<lit> keys --init` — it manages the shared gitignored `keys.env` at the project root and reports
presence as booleans (secrets never enter chat). Persist the live tiers to `loop.run.yaml`.

## Initialise the sandbox
Create the layout (extra `literature/` tree only when `<literature> = on`) and write the ledger headers:
```
<sandbox_root>/
├── loop.run.yaml       ← resolved bindings (written now)
├── results.tsv         ← experiment ledger, header only (written now)
├── literature/         ← (on only)
│   ├── corpus.tsv      ← findings ledger, header only (written now)
│   ├── .cache/         ← lit_search on-disk cache
│   ├── pdfs/           ← fallback PDF reads
│   └── text/           ← extracted LaTeX section text
└── iter1/              ← created at loop start
```
`results.tsv` header (tab-separated; the `literature_basis` column exists only when `<literature> = on`):
```
iter	<metric>	status	analysis_summary	[literature_basis	]description
```

## The loop (LOOP FOREVER — until interrupted)
Iteration 1 is always the **unmodified baseline**: skip change-planning and research (no diagnostics
yet to ground a change), but still write a baseline `plan.md` and run the **mandatory analysis** — it
produces the first empirical anchor that iteration 2 builds on. Everything in `<editable_files>` is fair
game (architecture, optimizer, hyperparameters, data pipeline, loss); the only constraints are that the
code runs without crashing and finishes within `<budget>`. **Simplicity criterion**: all else equal,
simpler is better — a 0.001 gain that adds 20 lines of hacky code is not worth it; a 0.001 gain (or an
equal metric) from *deleting* code is a `keep`.

Copy this checklist each iteration and tick items off:
- [ ] **1. Look at the state.** *branches*: `git log --oneline -5`. *snapshots*: confirm `iter<N>/`
      doesn't exist. Read iter N-1's analysis summary; (on) skim `corpus.tsv` for unimplemented keepers.
- [ ] **2. Plan one change** (iteration 1: SKIP — run baseline unmodified). Grounded in iter N-1's
      analysis. See **Planning a change** below; (on) it also runs the literature step.
- [ ] **3a. Snapshot / commit, then apply the one change.** *snapshots*: create
      `iter<N>/{code_snapshot,analysis,results}/`, copy every `<editable_files>` into `code_snapshot/`,
      copy `loop.run.yaml` to `iter<N>/`, then apply. *branches*: apply, then `git commit -am "<desc>"`.
      When implementing a published/library technique, ground it in a real current example or the actual
      library in the repo (read it first) — never write the API from memory.
- [ ] **3b. Write the analysis plan BEFORE the run** + add any instrumentation it needs. See **The
      analysis plan** below.
- [ ] **4. Run the experiment**, redirecting everything (never `tee`):
      `<entrypoint> > <sandbox_root>/iter<N>/<run_log> 2>&1` (or `run_with_timeout.sh` when time-gated).
      If it overruns, kill it and treat as a crash.
- [ ] **5. Read the metric**: `grep '^<metric>:' <sandbox_root>/iter<N>/<run_log>`. If empty,
      `tail -n 50 <run_log>`, read the trace, attempt one trivial fix (typo/import); if fundamentally
      broken, log `crash` and continue.
- [ ] **6. Analyse the results** — MANDATORY, produces real artifact files. See **Analysing** below.
- [ ] **7. Log to the ledger(s)** (untracked — never commit). See **Ledger**.
- [ ] **8. Keep or revert** (the change ran this iteration). Improved per `<metric_direction>` → `keep`,
      update current-best. Equal/worse/crash → `discard`/`crash`; *branches* `git reset --hard HEAD~1`,
      *snapshots* restore `<editable_files>` from `iter<N>/code_snapshot/`. Apply the simplicity
      criterion before logging `discard`. On a crash/OOM, fix with the *minimal* change that preserves
      the intent (OOM → smaller batch + grad-accum to hold effective batch) — never mutate the
      experiment into something the plan didn't call for.
- [ ] **9. Go to step 1** — the analysis from step 6 is the primary input to the next hypothesis.

### Planning a change (step 2 — iterations 2+)
The latest analysis sets the direction; it is the master input every iteration. Decide exactly **one**
lever, grounded in iter N-1's analysis. Other vetted ideas are queued, not bundled into one run.

**State explicitly** before applying:
- the one change and which `<editable_files>` it touches;
- the **empirical anchor** — a specific file + value/pattern from iter N-1's `results/` that motivates
  it. Every non-simplification change must cite an anchor; theoretical reasoning alone is insufficient.
  A *swing* to a different architecture is anchored too (a ceiling/structural finding, e.g. "the family
  plateaus at X with headroom" or "it fails exactly on cases needing Y"), not a local pathology.
- what you predict will happen and why the finding supports it.

**When `<literature> = off`:** that anchor is the whole basis — pick the change directly from the
analysis. Before writing the plan, scan prior analyses (`ls <sandbox_root>/iter*/analysis/*.py`) so you
don't repeat a diagnostic without a comparison reason.

**When `<literature> = on`:** after fixing the anchor, *ground the change in the literature* —
- **2a. Retire drift, then consult the backlog as a cache.** If the last kept change altered the
  architecture *family* (e.g. CNN→transformer), set `result=stale` for every unimplemented keeper whose
  `scope` is a non-matching architecture tag; `scope=agnostic` keepers (schedules, weight decay,
  augmentation, init *philosophies*) survive. Then check `corpus.tsv` for an unimplemented `keep`
  targeting the analysis's direction — reuse it **only if it still passes the gate (2c) against the
  CURRENT architecture** (re-validate now; a finding that no longer applies is retired, not forced in).
- **2b. Research the direction** (the default unless 2a yielded a still-valid lever). Turn the
  analysis's limitations into questions (tie limitations to questions), record them in
  `iter<N>/questions.md`, then dispatch **research subagents** — see `roles/research-subagent.md`
  (spawn-or-degrade: real isolated subagents on Claude Code, otherwise run the research inline in this
  context) at the dial's depth/effort (see that file's dial table for `<research_scale>`).
  Level 1 = high-level (architecture fit, prior approaches, does the literature show success); research
  L1 first — if it surfaces a compelling new direction that becomes the lever. Level 2 = specific
  micro-opts (init, weight-decay dynamics, attention/cache for the sequence length, norm placement,
  schedule). *Anti-rut: a keeper passed over for ~3 iterations, or no longer on any live direction, is
  retired (`result=stale`) so it stops resurfacing.*
- **2c. Evidence gate** (re-validated; consults history). Keep/reuse a finding only if **all** hold:
  `evidence.strength` is `moderate`/`strong` (not `weak`); `applicability_to_our_setup` transfers to
  the CURRENT data/model/budget; every `files_to_edit` is within `<editable_files>` and fits `<budget>`;
  and it is **not materially equivalent to a change already logged `no-effect`/`hurt`/`crashed`** in
  `corpus.tsv` (unless the finding explains why it differs now). Tag each kept finding's **`scope`**
  (`agnostic` or the current architecture tag) so drift retirement is mechanical. Record every finding
  in `corpus.tsv` (keep or reject); kept-but-unchosen findings stay queued (`implemented=n`,
  `result=pending`).
- **2d. Choose the single lever** from the keepers (backlog + new) — highest evidence × applicability ×
  gain-per-complexity. Add to the explicit statement above: the **literature basis** (kept finding +
  citation(s)), or `none` for a pure analysis-driven simplification/ablation; and the **verify-todo**
  (the metric/log/analysis from the finding's `how_to_verify` that will tell whether it helped). The
  literature basis is *additive* grounding — it never replaces the empirical anchor.

### The analysis plan (step 3b — written BEFORE the run)
Write `<sandbox_root>/iter<N>/analysis/plan.md` as a deliverables **table**, not prose — each row is a
hard commitment: a script you will write and run, the exact output file it produces, the question it
answers, and what each outcome would look like:

| script | output file | question it answers | expected if change helped | expected if not |
|--------|-------------|---------------------|---------------------------|-----------------|

The plan **must** include at least one diagnostic dimension **not measured in any prior iteration**
(the history scan enforces this); the "expected if not" column is mandatory (it forces you to define
falsification before seeing the result). When `<literature> = on`, also include the **verify-todo**
from 2d, and periodically (and whenever a swing is on the table) a **ceiling/headroom probe** — is the
current architecture near its limit? (train/val plateau, representation collapse, structural failure).

**Instrumentation (mandatory when needed).** If a planned measurement needs a metric/log not currently
produced (e.g. per-layer grad norms, per-class accuracy, `val_loss` alongside `val_acc`) and the
producing script is in `<editable_files>`, **add that logging NOW, before the run.** Writing the plan
first is what forces this — don't discover at analysis time that the number you need wasn't logged.

### Analysing (step 6 — MANDATORY; produces real artifacts)
This is the spine of the loop. **Do not proceed to step 7 until every row in `plan.md` has a
corresponding non-empty file in `iter<N>/results/`.** Analysis that didn't write a file did not happen.
- **6a. Execute the plan.** For each row, write the script in `iter<N>/analysis/` and run it,
  redirecting to `iter<N>/results/`. Diagnostic dimensions to draw from (choose what the hypothesis and
  results call for, not a fixed rotation): gradient norms/flow, activation stats/saturation, embeddings
  (PCA/CKA/collapse), error & confusion analysis, loss dynamics & **headroom**, weight/parameter stats,
  data profiling (auditing the data itself is one of the highest-yield diagnostics), compute profiling.
- **6b. Checklist.** `ls iter<N>/results/` against `plan.md`; write and run any missing deliverable now.
- **6c. Interpret against the plan.** For each row, did it match "expected if helped" or "if not"? A
  mismatch is information, not a failure.
- **6d.** (on) **Check the verify-todo** from 2d — did the change do what the literature predicted? This
  sets the finding's `result` in step 7.
- **6e. Opportunistic follow-up.** If something unexpected appears (odd loss shape, a consistently-wrong
  class, a layer behaving differently), write one more script to chase it — the most novel findings
  come from here.

Write a concise **analysis summary** (3–8 bullets): what you examined, the single most important
finding (expected or not), (on) whether the architecture is near its ceiling, and the specific
**empirical anchor** (file + value/pattern) that will motivate the next plan.

**Empirical-justification gate.** Before step 7, you must be able to complete this sentence with a real
file reference and a concrete value/pattern — not a theoretical argument:
> *"The next change will be X because the analysis showed Y (from `results/<file>`, value/pattern Z)."*

If you cannot, go back to 6a and run more analysis until you can. Proceeding without an empirical anchor
is the exact failure this loop is built to prevent.

**Forward-looking instrumentation.** After analysing, ask *"what would I wish I had logged?"* — if the
producing script is in `<editable_files>`, add it now (best-epoch checkpoint, extra per-epoch
diagnostics) so future analyses are richer. Adding instrumentation is a valid iteration on its own.

## Ledger
`<sandbox_root>/results.tsv`, tab-separated, never commas in free text. The `literature_basis` column
is present only when `<literature> = on`. Status ∈ {`keep`, `discard`, `crash`}; use `0.000000` for the
metric on crashes. For `branches`, the first column is the 7-char commit instead of the iter number.
```
iter	<metric>	status	analysis_summary	literature_basis	description
1	0.6320	keep	grad norms clean; no pathologies	none (baseline)	baseline
2	0.7050	keep	overfit on small data per val/train gap	Dosovitskiy 2020 ViT — aug+warmup	add RandAug + 3-ep warmup
3	0.7010	discard	warmup ok but LR too high; unstable	Loshchilov 2017 — decoupled wd	switch to AdamW wd=0.05
```
**`<sandbox_root>/literature/corpus.tsv`** (only when `<literature> = on`; tab-separated): a backlog of
vetted findings reused across iterations instead of re-researched. The orchestrator (not the subagent)
writes it and applies the final evidence gate, so verdicts are consistent across questions.
```
iter	level	paper_id	title	scope	relevance	verdict	implemented	result
2	649def…	1	An Image is Worth 16x16 Words	vit	high	keep	y	helped
3	a1c2…	2	Decoupled Weight Decay Regularization	agnostic	high	keep	y	no-effect
4	7d9e…	1	ConvNeXt blocks	cnn	low	keep	n	stale
```
Columns: `level` ∈ {1,2}; `scope` = `agnostic` or an architecture tag (drives drift retirement);
`relevance` ∈ {high,med,low}; `verdict` ∈ {keep,reject}; `implemented` ∈ {y,n}; `result` ∈
{helped,no-effect,hurt,pending,stale} (`stale` = retired on drift/expiry). Last row: a CNN keeper
retired after the architecture moved to ViT; the `agnostic` weight-decay finding survives drift.

Report the **best** iteration (not necessarily the last) when summarising progress. Do not commit
`results.tsv` or `literature/` to git — leave them untracked.

## Constraints
- **Only edit files in `<editable_files>`** — confirm before every edit, because everything else is
  read-only ground truth and the eval harness defines `<metric>`.
- **One change per iteration**, so each metric delta is attributable to one lever.
- **Analysis is mandatory every iteration** and must produce real files in `results/` (each `plan.md`
  row → a non-empty output file). A change with no analysis behind it is not allowed — it degrades the
  loop into blind iteration (or, when on, recipe-following that plateaus blind).
- **Every non-simplification change must cite an empirical anchor** (file + value/pattern) from that
  analysis; when on, the literature basis is additive, never a substitute. Record both in `results.tsv`.
- Do not install packages or add dependencies the project lacks; helper scripts (and the lit helper)
  stay stdlib-only.
- Always redirect training output to `<run_log>`; never use `tee`. The sandbox is self-contained — no
  `../` escapes.
- (on) Never print or commit API keys — `keys` reports presence only; `keys.env` lives at the project
  root and must stay gitignored. When a lit tool returns `{"error","fallback"}`, degrade to
  WebSearch/WebFetch; never fabricate citations — every cited paper must come from a real tool result.

## Stops
This loop runs **forever until the human interrupts it** — do not pause to ask "should I continue?" or
"is this a good stopping point?". The human may be away and expects autonomous work indefinitely. A
working result is the start of the next iteration, not the end. If you run out of ideas: re-read the
in-scope files for missed angles, go deeper on the analysis (gradients/activations/embeddings/errors
always surface something), combine previous near-misses from `results.tsv`, try more radical changes —
and when on, **go back to the literature**: crawl citation graphs deeper, read methodology of recent
work citing your approach, mine `corpus.tsv` for queued keepers, and combine recipes across papers.
