---
name: deepAgentMLAutoresearch
description: >
  Use when the user wants an autonomous ML research loop that grounds every change in
  the scientific literature. Like standardMLAutoresearch, each run is followed by a
  diagnostic analysis — but before forming the next hypothesis the agent turns its
  findings into questions, searches papers (Semantic Scholar, OpenAlex, arXiv, and
  optionally Perplexity Sonar / bgpt.pro), grades the evidence, and implements only
  what the literature actually supports. Loops forever until interrupted.
metadata:
  version: "0.1.0"
---

# Deep-Agent ML Autoresearch Loop

This loop is **literature-grounded and analysis-first**. Each iteration **plans a single
change** — grounded in the previous run's diagnostics *and* a targeted search of the
literature — then runs it, then analyses the result to motivate the next plan. Changes
are hypotheses backed by both your own evidence and prior work: not guesses, and not
reinventing published techniques. **One change per run**, so the metric move is
attributable to it.

**The analysis is the spine.** Every change must be anchored in a diagnostic finding
about *your* model — what is actually wrong, or where the headroom is, right now. The
literature adds known recipes *on top of* that anchor; it never substitutes for it.
Analysis is mandatory every iteration and must produce real artifact files (scripts +
outputs), not prose. A loop that does great lit review but skips analysis has degraded
into recipe-following — it can climb for a while on a known problem, then plateaus
blind. Do not let that happen.

**Assume your knowledge of specific library APIs and current methods is out of date.**
When a change implements a published technique, ground the *implementation* in a real
current example or the actual library in the repo — read it first; do not write it from
memory. Implementing from memory produces wrong imports and wrong argument names.

The literature search is the bottleneck, so it is built to be cheap: the shared
`literature-search` skill (`lit_search.py`, stdlib-only) with an on-disk cache, a triage-before-read
funnel, parallel research subagents that each return a strict recipe schema, and a
**backlog** (`corpus.tsv`) of vetted findings reused across iterations instead of
re-researched.

You are the researcher. Do not pause to ask for permission once the loop is running.

---

## 0. The literature toolchain (read once)

All literature access goes through the shared **`literature-search` skill** (`lit_search.py`) — it
is standard-library only (Python ≥3.9), needs no installs, and is **not vendored in this folder**.
Resolve these once at setup and reuse them everywhere:

- **`<lit_skill_dir>`** — where the `literature-search` skill is installed; after the repo install
  step it sits as a **sibling** of this loop, e.g. `~/.claude/skills/literatureSearch/` (adjust per host).
- **`<lit_py>`** — a Python ≥3.9 interpreter for the helper. Default `python3`. This is
  **independent of `<run_cmd>`** (the heavy ML env) — the helper is stdlib-only, so the
  literature tooling and training never interfere.
- **`<lit>`** — the standard invocation every caller uses:

  ```
  <lit_py> <lit_skill_dir>/lit_search.py --cache-dir <sandbox_root>/literature/.cache
  ```

  API keys load automatically from `keys.env` at the project root (see §1j); you do not
  pass `--env-file`.

**Check at setup whether the skill is installed** — probe `<lit_skill_dir>/lit_search.py`. If it is
missing, do not silently fall back — tell the user and offer the choice:
- **Install it** (recommended; this loop's grounding depends on it) — the repo install step
  (`cp -r agent-loop-skills/loops/* ~/.claude/skills/`, adjust per host), or just the one skill:
  `cp -r agent-loop-skills/loops/literatureSearch ~/.claude/skills/`. Then re-resolve `<lit_skill_dir>`.
- **Proceed without it** — use the host's WebSearch/WebFetch for all retrieval/synthesis (degraded).

Subcommands (all print JSON; on failure print `{"error","fallback"}` and exit non-zero
— when that happens, fall back to your built-in WebSearch / WebFetch):

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--source s2\|openalex\|both] [--year 2020-] [--min-citations N] [--limit N]` | **Discover** — ranked papers with title, TLDR, abstract, citations, arxiv_id. **Default `--source s2`**; this loop should pass **`--source both`** to widen discovery across S2 + OpenAlex. |
| `<lit> snippet "<q>" [--limit N]` | **Pinpoint a fact** — exact full-text passages from across the corpus (a hyperparameter value, a reported number). |
| `<lit> cite <paperId> --direction references\|citations\|recommend [--influential-only]` | **Expand** — walk the citation graph from an anchor paper. |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf] [--section <kw>]` | **Read a chosen paper** (see retrieval note below). |
| `<lit> ask "<q>" [--model sonar\|sonar-pro]` | **Synthesize** a high-level answer with citations (Level-1 questions; needs OpenRouter key). |
| `<lit> bgpt "<q>"` | **Evidence** — structured experimental results / limitations (free 50, then key). |
| `<lit> keys [--init]` | Report which API keys are present (booleans only). |

**Reading full text (internal mechanic — never surface this to the user).** To read a
paper's Methods/Results, prefer text over PDF, in this order:
1. `fulltext <id>` (auto) returns `html_url` + `ar5iv_url` — **WebFetch the html_url**
   (fallback ar5iv_url) and ask for the Methods/Experiments and Results sections.
2. If neither HTML renders, `fulltext <id> --mode latex` extracts the source sections
   to a text file — **Read that file**.
3. Only if both fail, `fulltext <id> --mode pdf` downloads the PDF — **Read** it.

For one specific fact, prefer `snippet` over reading a whole paper.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. You MUST ask every question below and wait for the
user's explicit answer. Do NOT infer, skip, or auto-apply any answer — even if you
think you know it from context. If you skip any question, you are doing it wrong.**

### 1.0 Detect host

Check whether the `AskUserQuestion` tool is available.

- **Yes → Claude Code path**: for each question, scan the project to infer a likely
  answer, then present it as the recommended option via `AskUserQuestion`.
- **No → plain-text path**: ask each question as a quoted prompt and wait for a reply.

Record as **`<host>`** = `claude-code` or `other`.

---

### 1a. What metric should the loop optimize?

**Claude Code**: scan editable files and any README for metric names. `AskUserQuestion`:
- Option 1 *(Recommended)*: inferred metric, e.g. `val_acc`
- Option 2–3: other plausible metrics
- Option 4: `Other — I'll specify`

**Other**: Ask:
> "What scalar metric should I optimize, and minimize or maximize?
>  (e.g. `val_loss` minimize, or `val_acc` maximize)"

Record as **`<metric>`** and **`<metric_direction>`** (`minimize` or `maximize`).

---

### 1b. What Python environment and run command?

**Claude Code**: scan for `pyproject.toml`, virtualenv paths, README run instructions.
`AskUserQuestion` with inferred command as recommended option.

**Other**: Ask:
> "What command runs one training experiment end to end?
>  (e.g. `/path/to/venv/bin/python train.py` or `uv run train.py`)"

Record as **`<run_cmd>`** / **`<entrypoint>`** (usually the same).

> **Remote sandboxes**: if training runs on a remote host, note the connection.
> `<run_cmd>` is dispatched there; everything else (including `lit_search.py`) runs
> locally.

---

### 1c. Which files are fair game to edit?

**Claude Code**: list candidate source files (model, config, training script). Exclude
data, logs, env files, and the evaluation harness. `AskUserQuestion` (multi-select):
one option per candidate file + `Other — I'll specify`.

**Other**: Ask:
> "Which files may I edit? (e.g. `model.py`, `config.yaml` — not the eval harness)"

Record as **`<editable_files>`**.

**FILE EDIT GUARD**: Before touching any file at any point — setup or loop — confirm it
is in `<editable_files>`. Everything else is read-only. No exceptions.

---

### 1d. Where should the sandbox live?

**Claude Code**: propose a default (e.g. `./sandbox/`). `AskUserQuestion` with it as
the recommended option.

**Other**: Ask:
> "Where should I keep the sandbox? Give me an absolute or relative path."

Record as **`<sandbox_root>`**.

---

### 1e. Iteration strategy — branches or snapshots?

**Claude Code**: check whether the working dir is a git repo and whether it is
gitignored. `AskUserQuestion`:
- Option 1 *(Recommended)*: whichever is safer, with a one-line reason
- Option 2: the other strategy

**Other**: Ask:
> "Track iterations via (a) **branches** — one commit per experiment; or
>  (b) **snapshots** — each iteration gets a folder in the sandbox?"

Record as **`<iter_strategy>`** = `branches` or `snapshots`.

If `branches`: propose a tag from today's date. Branch must not exist. Create it:
`git checkout -b autoresearch/<tag>`.

---

### 1f. Gate on time or epochs?

**Claude Code**: check the config/script for existing time or epoch settings.
`AskUserQuestion` with inferred value as recommended option.

**Other**: Ask:
> "Should each run be gated by wall-clock time (minutes) or a fixed epoch count?"

Record as **`<gate>`** = `time` or `epochs`, and **`<budget>`** = the limit.

If `time`: write `<sandbox_root>/run_with_timeout.sh`:
```bash
#!/usr/bin/env bash
timeout $(( <budget> * 60 )) <entrypoint> "$@"
```
Use the wrapper as the effective run command. Hard kill at `2 × <budget>` minutes.

If `epochs`: patch whichever file in `<editable_files>` controls the epoch count to cap
at `<budget>`. Do not touch files outside `<editable_files>`.

---

### 1g. What is the research domain?

The domain only **seeds better query phrasing** — it does **not** filter results.
Cross-domain transfer is valuable (a vision trick may apply to your tabular model), so
relevance ranking, not a domain fence, decides what surfaces.

**Claude Code**: infer the domain from the data/model/task (e.g. "small-image
classification", "tabular regression", "long-sequence forecasting"). `AskUserQuestion`
with the inferred phrase as the recommended option.

**Other**: Ask:
> "In one phrase, what's the problem domain? (Used only to phrase searches better —
>  papers from other fields are still fair game.)"

Record as **`<domain>`**.

---

### 1h. How deep should the literature review go? (the scaling dial)

One master dial scales the whole per-iteration research budget — number of questions,
number of subagents, and each subagent's depth — via countable caps.

**Claude Code** / **Other**: `AskUserQuestion` (or ask) with these presets:

| Preset | Questions/level | Subagents/Q | Depth (rounds · papers read · cite-hops) | effort |
|---|---|---|---|---|
| **low** | 1–2 | 1 | 3 · 0 · 0 (TLDR triage only) | low |
| **medium** *(Recommended)* | 2–3 | 1 | 8 · 3 · 1 | medium |
| **high** | 3–4 | 1–2 | 16 · 6 · 2 | high |
| **x-high** | 4–6 | 2 | 30 · 10+ · 3 (full influence crawl) | max |

Record as **`<research_scale>`**. The orchestrator may bump a single make-or-break
question one tier higher than the default.

---

### 1i. Resolve the literature interpreter and smoke-test the helper

Set **`<lit_py>`** = `python3` (override only if `python3` is <3.9; then use any ≥3.9
interpreter, e.g. the run env). Confirm the helper imports and lists subcommands:

```bash
<lit> --help
```

If this fails, the `literature-search` skill is not installed — handle it via §0's install-or-proceed
choice (install the skill, or proceed on WebSearch/WebFetch); do not silently continue.

---

### 1j. API keys (project-root file; you fill it yourself, secrets never enter chat)

Keys live in one `keys.env` at the **project root** (the nearest `.git` ancestor of the
working dir), shared by every skill in the project. It sits inside the repo, so it
**must be gitignored** — before writing it, ensure `keys.env` is in the project's
`.gitignore` (add the line if missing). All keys are **optional** — missing ones degrade
gracefully — but **Semantic Scholar's keyless pool is a saturated global limit**, so a
free `S2_API_KEY` is strongly recommended. (See `docs/api-keys.md` for the standard.)

1. **Check what's already there** (the file may already be populated from a prior setup
   or another skill in this project):
   ```bash
   <lit> keys
   ```
   If S2 (and whatever else you need) is already present, skip to step 4.
2. **Ensure `keys.env` is gitignored**, then **ensure it has slots** for this skill's
   keys (creates the file at the project root if missing; appends only missing keys —
   never clobbers existing ones):
   ```bash
   <lit> keys --init
   ```
   It prints the file path. Tell the user what each key adds:
   - `S2_API_KEY` — free, **recommended**; reliable semantic search + snippets + graph.
   - `OPENALEX_EMAIL` — free; faster OpenAlex.
   - `OPENROUTER_API_KEY` — paid; enables `ask` (Perplexity Sonar) for Level-1 synthesis.
   - `BGPT_API_KEY` — free 50 results then paid; structured experimental evidence.
3. **Ask the user to fill it themselves**, so secrets never enter this transcript:
   > "Open `keys.env` (at the project root) in your editor, paste the keys you want
   >  (S2 is free + recommended; the rest optional), and tell me when you're done."

   The in-session shortcut `! $EDITOR ./keys.env` opens it without leaving the loop.
   Offer to fill it for them only if they explicitly prefer.
4. **Verify and record — verbosely.** Run `<lit> keys` — it prints a per-key note
   (booleans only, never values): each key's `present` flag, a verbose `info` string
   (cost · what it enables · consequence if missing · where to get it), and `live` /
   `missing` lists. Report this back to the user **in full, key by key** — for each key
   state present/absent, what capability it turns on, and exactly what is lost without
   it (e.g. "BGPT_API_KEY missing → `bgpt` evidence extraction disabled after the free
   tier; everything else unaffected"). Then **persist it** to `schema.yaml` under
   `literature_tiers` so any later step can see it without re-checking. (`keys` is
   network-free — re-run it anytime to refresh.) Do not block on keys.

---

### 1k. Initialise sandbox

Create the layout and write the schema/ledgers:

```
<sandbox_root>/
├── schema.yaml          ← resolved bindings (written now)
├── results.tsv          ← experiment ledger, header only (written now)
├── literature/
│   ├── corpus.tsv       ← literature ledger, header only (written now)
│   ├── .cache/          ← lit_search on-disk cache
│   ├── pdfs/            ← downloaded PDFs (fallback reads)
│   └── text/            ← extracted LaTeX section text
└── iter1/               ← created at loop start

(API keys are NOT in the sandbox — they live in keys.env at the project root from §1j.)
```

**`results.tsv` header** (tab-separated, no commas):
```
iter	<metric>	status	analysis_summary	literature_basis	description
```

**`literature/corpus.tsv` header** (tab-separated):
```
iter	level	paper_id	title	scope	relevance	verdict	implemented	result
```
- `level` ∈ {1, 2} · `scope` = `agnostic` or an architecture tag (e.g. `cnn`, `vit`) —
  drives drift retirement · `relevance` ∈ {high, med, low}
- `verdict` ∈ {keep, reject} · `implemented` ∈ {y, n}
- `result` ∈ {helped, no-effect, hurt, pending, stale} (`stale` = retired on drift/expiry)

**`schema.yaml`**: write all resolved bindings, including `domain`, `research_scale`,
`lit_py`, and which key tiers are live. (Keys themselves live in `keys.env` at the
project root, never in the sandbox or schema.)

---

### 1l. Confirm and go

Print a summary of every resolved binding and the live/degraded literature tiers. **Do
not create files or start the loop until the user confirms.** Once confirmed, build the
sandbox and begin immediately.

---

## 2. The experiment loop

**`<run_log>`** is the file training output is captured in for an iteration. Default
`<sandbox_root>/iter<N>/<run_log>`; if the harness writes its own log elsewhere, use
that instead.

**Everything in `<editable_files>` is fair game**: architecture, optimizer,
hyperparameters, data pipeline, loss. Constraints: the code runs without crashing and
finishes within `<budget>`.

**Simplicity criterion**: all else equal, simpler is better. A 0.001 gain that adds 20
lines of hacky code is not worth it; a 0.001 gain from *deleting* code is. Equal metric
but simpler code is a `keep`.

**One change per iteration.** Plan and apply exactly one lever per run, so the metric
move is attributable. Other vetted findings are *queued* in `corpus.tsv` and pulled in
future iterations — not bundled into one run. (Decouple the axes, like `standard`/
`highTemp`.)

**The first run**: iteration 1 is the unmodified baseline — skip the change-planning/
research (no diagnostics to ground a change yet), but still do the **mandatory analysis**
(write a baseline `plan.md` in 3b, run it in step 6). The baseline analysis produces the
first empirical anchor that iteration 2's plan is built on, so it cannot be skipped.

**FILE EDIT GUARD**: confirm any file is in `<editable_files>` before editing it.

---

### LOOP FOREVER:

Each iteration is a self-contained cycle: **plan one change → apply → run → analyse →
keep/revert**. Research happens in the planning step (every iteration from 2 onward),
grounded in the *previous* iteration's analysis (already on disk).

**1. Look at the state.**
- *branches*: `git log --oneline -5` — note current branch and commit hash.
- *snapshots*: note iteration N; confirm `<sandbox_root>/iter<N>/` does not exist yet.
- Read the previous iteration's analysis summary (`iter<N-1>/results/`) and skim
  `corpus.tsv` for unimplemented keepers.

**2. Plan the change (iteration 1: SKIP — run the unmodified baseline).**

**The latest analysis sets the direction — it is the master input every iteration.**
The backlog is a *re-validated cache*, never a queue to drain. Decide exactly **one**
lever, grounded in iter N-1's analysis.

**2a. Retire drift, then consult the backlog as a cache.**
- **Drift retirement:** if the last kept change altered the architecture *family* (e.g.
  CNN→transformer), retire the now-stale backlog — set `result=stale` for every
  unimplemented keeper whose `scope` is a non-matching architecture tag. Architecture-
  agnostic keepers (`scope=agnostic` — schedules, weight decay, augmentation, init
  *philosophies*) survive.
- **Cache lookup:** given the direction the analysis points to, check `corpus.tsv` for
  an unimplemented `keep` finding that targets *that* direction. You may reuse it as the
  lever **only if it still passes the gate (2c) against the CURRENT architecture** — re-
  validate now; do not trust the as-of-discovery verdict. A finding that no longer
  applies is retired (`result=stale`), not forced in. Reuse is a cost win only when it
  genuinely still fits.

**2b. Research the direction (the default every iteration).** Unless 2a yielded a
still-valid, on-direction lever, research it. Generate questions from the analysis
limitations *and* higher-level considerations (tie limitations to questions where you
can), then dispatch **research subagents** (§3) at the dial's depth/effort (§1h). Record
questions in `iter<N>/questions.md`.
- **Level 1 — high-level** (architecture & prior art): does this architecture suit this
  data type? how have others approached similar problems? is there prior literature
  showing success? what are the common architectural families here? Research L1 first.
- **Level 2 — specific** (micro-opts): init scheme, weight-decay dynamics, attention/
  cache choice for the sequence length, normalization placement, schedule, etc.
- If L1 surfaces a compelling new direction, that becomes the lever and L2 questions
  *refine* it (in this or later iterations). If L1 yields nothing compelling, go to L2.

> Anti-rut: a backlog keeper passed over for ~3 iterations without being chosen, or no
> longer on any live direction, is retired (`result=stale`) so it stops resurfacing.
> The analysis decides what matters now — not the age of the queue.

**2c. Evidence gate (re-validated; consults history).** Keep or reuse a finding only if
**all** hold:
- `evidence.strength` is `moderate` or `strong` (not `weak`);
- `applicability_to_our_setup` transfers to the **CURRENT** data/model/budget — re-
  checked this iteration, not as of discovery;
- every `files_to_edit` is within `<editable_files>` and it fits `<budget>`;
- it is **not materially equivalent to a change already logged `no-effect`/`hurt`/
  `crashed` in `corpus.tsv`** — unless the finding explains why it would differ now.

Tag each kept finding's **`scope`**: `agnostic` if architecture-independent, else the
current architecture tag (so drift retirement in 2a is mechanical). Record every finding
in `corpus.tsv` (keep or reject); kept findings not chosen this iteration stay queued
(`implemented=n`, `result=pending`).

**2d. Choose the single lever and state the hypothesis.** From the keepers (backlog +
new), pick the **one** highest-value change (strong evidence × clear applicability ×
gain per unit of complexity). State explicitly:
- the one change and which `<editable_files>` it touches;
- the **empirical anchor** (file + value/pattern from iter N-1 `results/`);
- the **literature basis** (the kept finding + citation(s)), or `none` if the change is
  pure analysis-driven simplification/ablation;
- the **verify-todo**: the metric/log/analysis that will tell whether it helped (from
  the finding's `how_to_verify`) — checked in step 6.

Every non-simplification change **must cite an empirical anchor** (file + value/pattern
from the previous run's analysis). The literature basis is **additive** grounding — it
strengthens the change, it does not replace the anchor. (Pure simplification/ablation is
exempt.) A *swing* to a different architecture is anchored too — its anchor is a
ceiling/structural finding ("the current family plateaus at X with headroom to spare",
"it fails on exactly the cases requiring Y"), not a local pathology.

**3a. Snapshot / commit, then apply the one change.**
- *snapshots*: create `iter<N>/{code_snapshot,analysis,results}/`, copy every
  `<editable_files>` into `code_snapshot/`, copy `schema.yaml` to `iter<N>/`, then apply
  the change. *(Iteration 1: snapshot the unmodified baseline — no change.)*
- *branches*: apply the change, then `git commit -am "<short description>"`.

When the change uses a technique/library feature, **ground the implementation in a real
current example or the actual library** (read it) — don't write the API from memory.
After applying, do a quick fail-fast check (it imports/parses) before spending a run.

**3b. Write the analysis plan (BEFORE the run) and add any needed instrumentation.**
Write `iter<N>/analysis/plan.md` as a deliverables table — each row is a commitment:

| script | output file | question it answers | expected if the change helped | expected if not |
|--------|-------------|---------------------|-------------------------------|-----------------|

The plan **must** include:
- the **verify-todo** metric(s) from 2d (does the change do what the literature predicted?);
- **at least one diagnostic dimension not measured in any prior iteration** (scan
  `iter*/analysis/` to avoid repeats);
- periodically (and whenever a swing is on the table) a **ceiling/headroom probe** — is
  the current architecture near its limit? (train/val plateau, representation collapse,
  structural failure mode). This is what produces the anchor that licenses a *swing*.

**Instrumentation (mandatory when needed).** If any planned measurement needs a metric
or log that is not currently produced — e.g. logging `val_loss` alongside `val_acc`,
per-layer grad norms, per-class accuracy — and the producing script is in
`<editable_files>`, **add that logging NOW, before the run.** Writing the plan first is
what forces this; do not discover at analysis time that the number you need wasn't
logged. (Iteration 1 writes a baseline-characterization plan so it still produces the
first empirical anchor.)

**4. Run the experiment — redirect everything, never use `tee`.**
```bash
# time-gated
<sandbox_root>/run_with_timeout.sh > <sandbox_root>/iter<N>/<run_log> 2>&1
# epoch-gated
<entrypoint> > <sandbox_root>/iter<N>/<run_log> 2>&1
```
If the run has not terminated when it should have, kill it and treat as a crash.

**5. Read the metric.**
```bash
grep '^<metric>:' <sandbox_root>/iter<N>/<run_log>
```
If empty: `tail -n 50 <run_log>`, read the trace, attempt one trivial fix (typo,
missing import). If fundamentally broken, log as `crash` and continue.

**6. Analyse the results — MANDATORY; produces real artifacts.**

This is the spine of the loop, not an afterthought. **Do not proceed to step 7 until
every row in `plan.md` has a corresponding non-empty file in `iter<N>/results/`.** No
hand-waving — analysis that didn't write a file did not happen.

- **6a. Execute the plan.** For each row in `plan.md`, write the script in
  `iter<N>/analysis/` and run it, redirecting output to `iter<N>/results/`. Diagnostic
  dimensions to draw from: gradient norms/flow, activation stats/saturation, embeddings
  (PCA/CKA/collapse), error & confusion analysis, loss dynamics & **headroom**,
  weight/parameter stats, data profiling, compute profiling. **Audit the data itself**
  when relevant — looking at the data is one of the highest-yield diagnostics.
- **6b. Checklist.** `ls iter<N>/results/` and cross-reference `plan.md`. Any missing
  deliverable: write and run it now before continuing.
- **6c. Interpret against the plan.** For each row, did the result match "expected if
  the change helped" or "expected if not"? A mismatch is information, not a failure.
- **6d. Check the verify-todo** (from 2d): did the change do what the literature
  predicted? This sets the finding's `result` in step 7.
- **6e. Opportunistic follow-up.** If something unexpected appears, write one more
  script to chase it — this is where the most novel findings come from.

Write a concise **analysis summary** (3–8 bullets): what you examined, the most
important finding (expected or not), whether the current architecture is near its
ceiling, and the specific **empirical anchor** (file + value/pattern) that will motivate
the next iteration's plan.

**Empirical-justification gate.** Before step 7, you must be able to complete this
sentence with a real file reference and a concrete value/pattern — not a theoretical
argument:
> *"The next change will be X because the analysis showed Y (from `results/<file>`,
> value/pattern Z)."*

If you cannot, go back to 6a and run more analysis until you can. Proceeding without an
empirical anchor is the exact failure this loop is built to prevent.

**Forward-looking instrumentation.** After analysing, ask *"what would I wish I had
logged?"* — if the producing script is in `<editable_files>`, add it now (best-epoch
checkpoint, extra per-epoch diagnostics) so future analyses are richer. (Instrumentation
needed for *this* iteration's plan was already added in 3b.)

**7. Log to the ledgers. Do NOT commit them — leave untracked.**

`results.tsv` (one tab-separated row):
- *snapshots*: `<N>  <metric>  <status>  <analysis summary>  <literature basis>  <description>`
- *branches*: `<commit>  <metric>  <status>  <analysis summary>  <literature basis>  <description>`

`<status>` ∈ {`keep`, `discard`, `crash`}. Use `0.000000` for the metric on crashes.
`<literature_basis>` is a short cite (e.g. `Dosovitskiy 2020 ViT — warmup+strong aug`)
or `none` for empirical/simplification changes.

`corpus.tsv`: set this iteration's lever finding to `implemented=y` and write its
`result` now that the metric is known — `helped` / `no-effect` / `hurt` (a crash counts
as `hurt`). This is how the loop learns which sources pay off and avoids re-trying
failures (the 2c gate reads it).

**8. Keep or revert** (in-iteration — the change ran this iteration):
- **Improved** (per `<metric_direction>`): status `keep`; update current-best.
- **Equal or worse / crash**: status `discard`/`crash`;
  *branches* `git reset --hard HEAD~1`; *snapshots* restore `<editable_files>` from
  `iter<N>/code_snapshot/`. Apply the simplicity criterion before logging `discard`.

**Scope-preserving recovery.** If the change crashed/OOM'd, fix it with the *minimal*
change that preserves the change's intent (e.g. OOM → reduce batch size + raise grad-
accum to hold effective batch; not silently swapping the technique for a different one).
Never mutate the experiment into something the plan didn't call for. Diagnose the real
error; do not blind-retry the same thing.

If stuck (same ideas failing), you may rewind further — very sparingly. It is almost
always better to let analysis + literature surface a new angle.

**9. Go to step 1** for the next iteration.

---

**NEVER STOP**: Once the loop has begun, do NOT pause to ask "should I continue?". The
human may be asleep and expects you to work **indefinitely** until manually stopped. The
workflow is a loop, not a checklist — a working result is the start of the next
iteration, not the end. If you run out of ideas, **go back to the literature**: crawl
citation graphs deeper to find papers you haven't read, read the methodology sections of
recent work that cites your current approach, and try *combining* recipes from different
papers. Also: re-read the in-scope files, mine `corpus.tsv` for queued keepers, re-read
the training logs for clues, and combine previous near-misses. There is almost always a
paper you haven't read yet. The loop runs until interrupted.

---

## 3. The research subagent (spawn-or-degrade)

For each question, run a researcher. **Spawn** a real isolated subagent where the host
supports it (Claude Code: the `Agent` tool, with `effort` set per the dial); otherwise
**degrade** to doing the funnel inline. Either way it follows the same protocol and
returns the same schema.

**Give the subagent:** the question, its `abstraction_level`, the `<domain>` phrasing,
the resolved `<lit>` command, its depth caps (rounds · papers · hops) and effort from
the dial, the contents of `literature_schema.json`, and the relevant analysis summary.

**Retrieval funnel (the approved order):**
```
1. DISCOVER   <lit> search --source both  → N papers (title, TLDR, abstract, citations, arxiv_id)
2. TRIAGE     read TLDRs/abstracts → pick the top-k promising   (no full text yet)
3. GO DEEPER  (by need, within depth caps)
     a. need a specific fact/number  → <lit> snippet  (passages across the corpus)
     b. need a paper's full method   → fulltext (HTML→LaTeX→PDF) of THAT paper
4. EXPAND     <lit> cite (references / citations / recommend) → walk from an anchor
```

**Tune the funnel to the level:**
- **Level 1** (landscape): `<lit> ask` (Sonar) first for a fast synthesis with
  citations, then `search` for survey/landmark papers, then `cite` to walk the graph to
  recent downstream work. Verify Sonar's citations through `search`/`fulltext`.
- **Level 2** (exact values): `snippet` first — it returns the exact passages with the
  number you need — then `fulltext` on the one or two papers that matter.

**Read methodology, not abstracts.** Triage on TLDR/abstract, but extract recipes from
the **Methods/Experiments/Results** sections. Prefer recent papers with strong reported
results, high citations, and reputable venues. **Attribute every finding to a specific
reported result** ("dataset X + method Y → 85.3% on benchmark Z") — a recipe with no
number behind it is weak evidence.

**Evidence corroboration (high / x-high).** For a top candidate, use `<lit> bgpt` to
pull structured experimental results / limitations and corroborate the finding's
`reported_gain` and `has_ablation`.

**Tool gotchas (verified — heed these):**
- `cite`/`recommend` need a **Semantic Scholar** `paperId`. An **OpenAlex id will not
  resolve** — for OpenAlex/DOI-sourced papers, call `cite "DOI:10.xxxx/..."` or
  `cite "ARXIV:2010.11929"` (S2 accepts those prefixes).
- `fulltext` HTML/LaTeX is **arXiv-only**. For a non-arXiv but **open-access** paper,
  read its `pdf_url` (from `search`) via `fulltext --mode pdf <pdf_url>`. Paywalled
  papers: rely on the abstract + `snippet`.
- **S2 is globally rate-limited to ~1 req/s** (shared across all S2 calls and all
  parallel subagents). Use **OpenAlex for breadth** (no such limit); reserve S2 for
  relevance ranking, `snippet`, and `cite` where it is uniquely valuable.

**Depth caps** (from the dial): at most `<rounds>` tool calls, read at most `<papers>`
papers' full text, follow at most `<hops>` citation hops. Stop when caps are hit.

**Repetition guard:** if a search/snippet/cite returns the same or no new information
as a prior call, do not repeat it — change strategy (different query, different source,
a citation hop) or stop. Identical consecutive calls or an A→B→A→B cycle means you are
stuck: stop and summarize what you have.

**Output:** return an object validated against `literature_schema.json` — ranked
findings, each with claim, recipe (exact hyperparameters where the source gives them),
evidence (strength / agreement / ablation / reported gain), citations (with the
supporting snippet), applicability, proposed change, files-to-edit, how-to-verify, and
a keep/reject verdict. Findings only — raw search dumps are not the deliverable. An
empty `findings` array is a valid, honest result ("no compelling evidence").

**Record-keeping:** the orchestrator (not the subagent) writes `corpus.tsv` and applies
the final evidence gate, so verdicts are consistent across questions.

---

## 4. Scaling dial reference

`<research_scale>` presets (countable caps; the orchestrator may bump one critical
question up a tier):

| Preset | Questions/level | Subagents/Q | rounds · papers · hops | effort |
|---|---|---|---|---|
| low | 1–2 | 1 | 3 · 0 · 0 | low |
| medium | 2–3 | 1 | 8 · 3 · 1 | medium |
| high | 3–4 | 1–2 | 16 · 6 · 2 | high |
| x-high | 4–6 | 2 | 30 · 10+ · 3 | max |

---

## 5. Ledger formats

**`results.tsv`** (tab-separated, never commas):
```
iter	<metric>	status	analysis_summary	literature_basis	description
1	0.6320	keep	grad norms clean; no pathologies	none (baseline)	baseline
2	0.7050	keep	overfit on small data per val/train gap	Dosovitskiy 2020 ViT — strong aug + warmup	add RandAug + 3-ep warmup
3	0.7010	discard	warmup ok but LR too high; unstable	Loshchilov 2017 — decoupled wd	switch to AdamW wd=0.05
```

**`literature/corpus.tsv`** (tab-separated):
```
iter	level	paper_id	title	scope	relevance	verdict	implemented	result
2	1	649def…	An Image is Worth 16x16 Words	vit	high	keep	y	helped
2	1	0b3f…	MLP-Mixer	mlp	med	reject	n	-
3	2	a1c2…	Decoupled Weight Decay Regularization	agnostic	high	keep	y	no-effect
4	1	7d9e…	ConvNeXt blocks	cnn	low	keep	n	stale
```
(Last row: a CNN-scoped keeper retired to `stale` after the architecture moved to ViT —
drift retirement, step 2a. The `agnostic` weight-decay finding survives drift.)

Do not commit `results.tsv` or `literature/` to git. Leave them untracked.

---

## 6. Hard constraints (never violate)

- **Only edit files in `<editable_files>`.** Confirm before every edit.
- Do not install new packages or add dependencies not already present. `lit_search.py`
  is stdlib-only and needs none.
- Do not modify the evaluation harness — `<metric>` is the ground truth.
- Do not pause the loop to ask the human for direction.
- Always redirect training output to `<run_log>`. Never use `tee`.
- The sandbox must be self-contained — no `../` escapes.
- **Analysis is mandatory every iteration** and must produce real files in `results/`
  (each `plan.md` row → a non-empty output file). A change with no analysis behind it is
  not allowed.
- Every non-simplification change **must cite an empirical anchor** from that analysis
  (file + value/pattern). The literature basis is additive, never a substitute. Record
  both in `results.tsv`.
- Never print or commit API keys. `keys` reports presence only. Keys live in `keys.env`
  at the project root, which must stay gitignored.
- When a literature tool returns `{"error","fallback"}`, fall back to WebSearch /
  WebFetch — never fabricate citations. Every cited paper must come from a real tool
  result you actually retrieved.
