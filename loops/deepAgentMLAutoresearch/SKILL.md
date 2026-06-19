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

This loop is **analysis-first and literature-grounded**. Every experiment is followed
by a diagnostic pass (as in `standardMLAutoresearch`), and then by a **literature
review**: the analysis findings become questions, the questions drive a paper search,
and the next change is whatever the evidence most supports. Changes are hypotheses
grounded in both your own diagnostics *and* prior work — not guesses, and not
reinventing published techniques.

The literature search is the bottleneck, so it is built to be cheap: a self-contained
helper (`lit_search.py`, stdlib-only) with an on-disk cache, a triage-before-read
funnel, and parallel research subagents that each return a strict recipe schema.

You are the researcher. Do not pause to ask for permission once the loop is running.

---

## 0. The literature toolchain (read once)

All literature access goes through `lit_search.py` in this skill folder. It is
standard-library only (Python ≥3.9) and needs no installs. Resolve these once at setup
and reuse them everywhere:

- **`<skill_dir>`** — the folder containing this `SKILL.md` and `lit_search.py`.
- **`<lit_py>`** — a Python ≥3.9 interpreter for the helper. Default `python3`. This is
  **independent of `<run_cmd>`** (the heavy ML env) — the helper is stdlib-only, so the
  literature tooling and training never interfere.
- **`<lit>`** — the standard invocation every caller uses:

  ```
  <lit_py> <skill_dir>/lit_search.py --cache-dir <sandbox_root>/literature/.cache
  ```

  API keys load automatically from the shared global file
  `~/.config/agent-loop-skills/keys.env` (see §1j); you do not pass `--env-file`.

Subcommands (all print JSON; on failure print `{"error","fallback"}` and exit non-zero
— when that happens, fall back to your built-in WebSearch / WebFetch):

| Subcommand | Use |
|---|---|
| `<lit> search "<q>" [--source both\|s2\|openalex] [--year 2020-] [--min-citations N] [--limit N]` | **Discover** — ranked papers with title, TLDR, abstract, citations, arxiv_id. |
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
<lit_py> <skill_dir>/lit_search.py --help
```

If this fails, stop and report it — the loop cannot ground itself without the helper.

---

### 1j. API keys (shared global file; you fill it yourself, secrets never enter chat)

Keys live in ONE shared file reused by every skill and project:
`~/.config/agent-loop-skills/keys.env` (honoring `$XDG_CONFIG_HOME`). It is outside any
repo, so it can't be committed. All keys are **optional** — missing ones degrade
gracefully — but **Semantic Scholar's keyless pool is a saturated global limit**, so a
free `S2_API_KEY` is strongly recommended. (See `docs/api-keys.md` for the standard.)

1. **Check what's already there** (the global file may already be populated from a prior
   setup or another skill):
   ```bash
   <lit> keys
   ```
   If S2 (and whatever else you need) is already present, skip to step 4.
2. **Ensure the file has slots** for this skill's keys (creates the file if missing;
   appends only missing keys — never clobbers existing ones):
   ```bash
   <lit_py> <skill_dir>/lit_search.py keys --init
   ```
   It prints the file path. Tell the user what each key adds:
   - `S2_API_KEY` — free, **recommended**; reliable semantic search + snippets + graph.
   - `OPENALEX_EMAIL` — free; faster OpenAlex.
   - `OPENROUTER_API_KEY` — paid; enables `ask` (Perplexity Sonar) for Level-1 synthesis.
   - `BGPT_API_KEY` — free 50 results then paid; structured experimental evidence.
3. **Ask the user to fill it themselves**, so secrets never enter this transcript:
   > "Open `~/.config/agent-loop-skills/keys.env` in your editor, paste the keys you
   >  want (S2 is free + recommended; the rest optional), and tell me when you're done."

   The in-session shortcut `! $EDITOR ~/.config/agent-loop-skills/keys.env` opens it
   without leaving the loop. Offer to fill it for them only if they explicitly prefer.
4. **Verify** (booleans only — you never see the values) and report live vs degraded:
   ```bash
   <lit> keys
   ```
   Report which tiers are **live** vs **degraded**, and proceed. Do not block on keys.

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

(API keys are NOT in the sandbox — they live in the shared global
~/.config/agent-loop-skills/keys.env from §1j.)
```

**`results.tsv` header** (tab-separated, no commas):
```
iter	<metric>	status	analysis_summary	literature_basis	description
```

**`literature/corpus.tsv` header** (tab-separated):
```
iter	level	paper_id	title	relevance	verdict	implemented	result
```
- `level` ∈ {1, 2} · `relevance` ∈ {high, med, low} · `verdict` ∈ {keep, reject}
- `implemented` ∈ {y, n} · `result` ∈ {helped, no-effect, hurt, pending}

**`schema.yaml`**: write all resolved bindings, including `domain`, `research_scale`,
`lit_py`, and which key tiers are live. (Keys themselves live in the global
`~/.config/agent-loop-skills/keys.env`, never in the sandbox or schema.)

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

**The first run**: always run the script unmodified to establish the baseline (no
literature review on iteration 1 — there are no findings to ground yet).

**FILE EDIT GUARD**: confirm any file is in `<editable_files>` before editing it.

---

### LOOP FOREVER:

**1. Look at the state.**
- *branches*: `git log --oneline -5` — note current branch and commit hash.
- *snapshots*: note iteration N; confirm `<sandbox_root>/iter<N>/` does not exist yet.

**2. Run the experiment — redirect everything, never use `tee`.**
```bash
# time-gated
<sandbox_root>/run_with_timeout.sh > <sandbox_root>/iter<N>/<run_log> 2>&1
# epoch-gated
<entrypoint> > <sandbox_root>/iter<N>/<run_log> 2>&1
```
(For iteration 1 this is the unmodified baseline. For 2+, you have already applied the
change decided at the end of the previous iteration.)

If the run has not terminated when it should have, kill it and treat as a crash.

**3. Read the metric.**
```bash
grep '^<metric>:' <sandbox_root>/iter<N>/<run_log>
```
If empty: `tail -n 50 <run_log>`, read the trace, attempt one trivial fix (typo,
missing import). If fundamentally broken, log as `crash` and continue.

**4. Analyse the results.** (Same diagnostic discipline as `standardMLAutoresearch`.)

Write analysis scripts to `<sandbox_root>/iter<N>/analysis/` and their outputs to
`<sandbox_root>/iter<N>/results/`. Draw from: gradient diagnostics, activation
analysis, embeddings, error/confusion analysis, loss dynamics, weight/parameter stats,
data profiling, compute profiling — whatever explains *why* this result happened.

Write a concise **analysis summary** (3–8 bullets): what you examined, the most
important finding (expected or not), and the specific empirical anchor (file + value/
pattern) that will motivate the next change.

**Extend the training log if it would help future analysis.** If the script that
produces the log/metrics is in `<editable_files>`, add diagnostics (per-layer grad
norms, per-class metrics, train/val gap, best-epoch checkpoint). Richer logs compound.

**5. LITERATURE REVIEW PHASE.** *(This is what makes this loop "deep". Run it every
iteration from iteration 2 onward.)*

**5a. Generate questions at two abstraction levels.** Derive questions from the
analysis limitations *and* from higher-level considerations — don't draw them only from
the limitations, but tie observed limitations to the questions where you can.

- **Level 1 — high-level** (architecture & prior art): Does this architecture suit this
  data type? How have people approached similar problems? Is there prior literature
  showing success? What are the common architectural families for a problem of this
  type? Decompose the problem into its high-level components and ask about each.
- **Level 2 — specific** (micro-optimizations): optimal weight init for models like
  this, weight-decay dynamics, KV-cache construction, attention choice given sequence
  length, normalization placement, schedule, etc. — direct optimizations on the current
  architecture.

Generate `<questions/level>` per the scaling dial (§1h). Write them to
`<sandbox_root>/iter<N>/questions.md`.

**5b. Research Level 1 first.** For each L1 question, dispatch a **research subagent**
(§3) at the dial's depth/effort. Collect their returned findings (validated against
`literature_schema.json`).

**5c. Apply the evidence gate to L1 findings.** Keep a finding only if **all** hold:
- `evidence.strength` is `moderate` or `strong` (not `weak`);
- `applicability_to_our_setup` genuinely transfers to this data/model/budget;
- every `files_to_edit` is within `<editable_files>` and the change fits `<budget>`.

Otherwise reject it. Record every finding in `corpus.tsv` (keep or reject).

**5d. Implement L1 keepers, then go to Level 2.**
- If there are L1 keepers: implement the highest-value one(s) this iteration, then ask
  L2 questions that *refine* the chosen direction.
- If there are **no** L1 keepers: skip straight to L2 (micro-optimizations on the
  current architecture), exactly as you would when the high level is already settled.

**5e. Research Level 2** the same way (subagents → findings → evidence gate → record).

**5f. Compile and pick levers.** From all kept findings, select the **highest-value
change(s)** for the next iteration — prefer strong evidence, clear applicability, and
high expected gain per unit of complexity. For each selected lever, add a
**verification todo**: the metric/log/analysis to add or watch next run to tell whether
it actually helped (from the finding's `how_to_verify`). Add these to
`<sandbox_root>/iter<N>/questions.md` under "Verify next run".

> Cadence: the full review runs every iteration. If a `keep` is being *ablated* or
> re-tested under a perturbation, a lighter review (or none) is fine — say so explicitly
> in the hypothesis.

**6. Form the grounded hypothesis.** State explicitly:
- The change you will make and which `<editable_files>` it touches.
- **The empirical anchor** (file + value/pattern from `results/`) — as in `standard`.
- **The literature basis** — the kept finding(s) and citation(s) that support it.

A change with neither a strong empirical anchor nor literature support is not allowed —
go back to analysis or research. (Pure simplification/ablation is exempt.)

**7. Snapshot / commit, then apply the change.**
- *snapshots*: create `iter<N>/{code_snapshot,analysis,results}/`, copy every
  `<editable_files>` into `code_snapshot/`, copy `schema.yaml` to `iter<N>/`, then apply
  the change to the working files. *(For iteration 1, the snapshot is the baseline; the
  change is applied at the END of iteration 1 for use in iteration 2.)*
- *branches*: apply the change, then `git commit -am "<short description>"`.

**8. Log to the ledgers. Do NOT commit them — leave untracked.**

`results.tsv` (one tab-separated row):
- *snapshots*: `<N>  <metric>  <status>  <analysis summary>  <literature basis>  <description>`
- *branches*: `<commit>  <metric>  <status>  <analysis summary>  <literature basis>  <description>`

`<status>` ∈ {`keep`, `discard`, `crash`}. Use `0.000000` for the metric on crashes.
`<literature_basis>` is a short cite (e.g. `Dosovitskiy 2020 ViT — warmup+strong aug`)
or `none` if the change was empirical/simplification only.

`corpus.tsv`: ensure every finding considered this iteration has a row; when a prior
lit-driven change's result is now known, **update its `result`** field
(helped/no-effect/hurt) so the loop learns which sources pay off.

**9. Keep or revert** (this happens after the *next* run reveals the metric; track it):
- **Improved** (per `<metric_direction>`): status `keep`; update current-best.
- **Equal or worse / crash**: status `discard`/`crash`;
  *branches* `git reset --hard HEAD~1`; *snapshots* restore `<editable_files>` from
  `iter<N>/code_snapshot/`. Apply the simplicity criterion before logging `discard`.

  If stuck (same ideas failing), you may rewind further — very sparingly. It is almost
  always better to let analysis + literature surface a new angle.

**10. Go to step 1** for the next iteration.

---

**NEVER STOP**: Once the loop has begun, do NOT pause to ask "should I continue?". The
human may be asleep and expects you to work **indefinitely** until manually stopped. If
you run out of ideas: think harder, re-read the in-scope files, mine `corpus.tsv` for
kept-but-not-yet-tried findings, follow citation graphs deeper, raise `research_scale`
for one hard question, or combine previous near-misses. The loop runs until interrupted.

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
1. DISCOVER   <lit> search  → N papers (title, TLDR, abstract, citations, arxiv_id)
2. TRIAGE     read TLDRs/abstracts → pick the top-k promising   (no full text yet)
3. GO DEEPER  (by need, within depth caps)
     a. need a specific fact/number  → <lit> snippet  (passages across the corpus)
     b. need a paper's full method   → fulltext (HTML→LaTeX→PDF) of THAT paper
4. EXPAND     <lit> cite (references / citations / recommend) → walk from an anchor
```
For Level-1 questions, `<lit> ask` (Sonar) is a fast first pass to synthesize the
landscape — then verify its citations through `search`/`fulltext`.

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
iter	level	paper_id	title	relevance	verdict	implemented	result
2	1	649def…	An Image is Worth 16x16 Words	high	keep	y	helped
2	1	0b3f…	MLP-Mixer	med	reject	n	-
3	2	a1c2…	Decoupled Weight Decay Regularization	high	keep	y	no-effect
```

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
- A non-simplification change must have an empirical anchor **or** a literature basis;
  prefer both. Record the basis in `results.tsv`.
- Never print or commit API keys. `keys` reports presence only. Keys live in the shared
  global `~/.config/agent-loop-skills/keys.env`, outside any repo.
- When a literature tool returns `{"error","fallback"}`, fall back to WebSearch /
  WebFetch — never fabricate citations. Every cited paper must come from a real tool
  result you actually retrieved.
