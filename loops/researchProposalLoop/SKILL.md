---
name: researchProposalLoop
description: >
  Use when the user has a research proposal (problem + proposed methodology + planned
  experiments) and wants it iteratively strengthened until it clears a passing grade. Each
  iteration runs ScholarEval (a faithful reimplementation of arXiv 2510.16234) to produce
  literature-grounded Soundness + Contribution feedback, a Judge grades that feedback into a
  0-100 against a fixed rubric, and a Reviser rewrites the proposal to fix the worst points
  without diluting the research question. Loops until the grade clears <pass_threshold> or the
  budget is hit.
metadata:
  version: "0.1.0"
---

# Research Proposal Loop

Artifact = a **research proposal**. The feedback signal = **ScholarEval** (literature-grounded
Soundness + Contribution), turned into a **graded score** by a **Judge** against the fixed
`rubric.md`. The loop **evaluates → grades → revises** until the grade clears your threshold.

**North star.** Clearing the threshold is the stopping condition, not the goal. The goal is to
transform the proposal into the **strongest, most novel, genuinely publishable** version it can
honestly become — one whose results, if executed, would plausibly be a **field-advancing,
first-of-its-kind, or state-of-the-art contribution**. Every revision should ask "does this make
the work more significant and more novel?", not merely "does this patch a flaw?". Crucially,
this is **grounded ambition**: the lift comes from a better-justified method, a sharper and more
defensible novelty claim, stronger baselines and evaluation — all backed by real retrieved
evidence. It is **never** hype, inflated claims, or novelty asserted beyond what the literature
supports — overclaiming lowers the grade (evidence gate + Contribution axis), it does not raise
it. Push the idea to be excellent and true at the same time.

The cast and files (all in this folder):
- `roles/ScholarEval.md` — the two-module literature-grounded evaluator (produces feedback).
- `roles/Judge.md` — grades the feedback → 0–100 + ranked fixes (decides pass/fail).
- `roles/Reviser.md` — rewrites the proposal to address the fixes (guards the research intent).
- `rubric.md` — the **fixed** grading rubric (the Judge never edits it).
- `schemas/scholareval.schema.json` — the ScholarEval evaluation (example in `roles/ScholarEval.md`).
- `schemas/verdict.schema.json` — the Judge's graded verdict (example in `roles/Judge.md`).
- `lit_search.py` + `lit/` — the vendored **Semantic Scholar + arXiv** retrieval backend.

Spawn-or-degrade: on Claude Code, spawn ScholarEval / Reviser as real `Agent` subagents;
otherwise adopt each role inline. **You are the orchestrator** (and the Judge).

---

## 0. The literature toolchain (read once)

All literature access goes through `lit_search.py` in this folder — stdlib-only, no installs.
Resolve once and reuse:
- **`<skill_dir>`** — this folder (contains `SKILL.md`, `lit_search.py`).
- **`<lit_py>`** — `python3` (any ≥3.9 interpreter).
- **`<lit>`** — `<lit_py> <skill_dir>/lit_search.py --cache-dir <sandbox_root>/literature/.cache`

Subcommands (all print JSON; on failure print `{"error","fallback"}` and exit non-zero —
then fall back to your built-in **WebSearch/WebFetch**):

| Subcommand | Use in ScholarEval |
|---|---|
| `<lit> search "<q>" [--year 2020-] [--min-citations N] [--limit N]` | discover related papers (titles, TLDR, abstract, citations, arxiv_id) |
| `<lit> snippet "<q>" [--limit N]` | pinpoint a methods/results passage — the **Soundness** evidence (GROBID substitute) |
| `<lit> cite <paperId> --direction references\|citations\|recommend` | walk the citation graph — the **Contribution** augmentation step |
| `<lit> fulltext <arxivId> [--mode auto\|latex\|pdf]` | read a specific paper's Methods/Results (the deep GROBID stand-in) |
| `<lit> keys [--init]` | report which API keys are present (booleans only) |

This is the **S2 + arXiv stack** (per the paper's reliance on Semantic Scholar). `S2_API_KEY`
is free and strongly recommended (snippet + cite are the two ScholarEval-defining moves); it
degrades to the saturated keyless pool, then to WebSearch/WebFetch, if absent.

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question and wait for the user's answer. Do NOT
infer or auto-apply. If you skip any, you are doing it wrong.**

### 1.0 Detect host
Check whether `AskUserQuestion` is available. **Yes → Claude Code path** (infer + recommend
via `AskUserQuestion`); **No → plain-text path** (ask as quoted prompts). Record **`<host>`**.

### 1a. The proposal
Record **`<proposal_path>`** — a file with the problem, proposed methodology, and planned
experiments. *Claude Code*: scan for a likely `.md`/`.txt`/`.pdf` and recommend it. *Other*:
*"Where is the research proposal? (a file path, or paste it and I'll save it.)"* If only prose
is pasted, save it to `<sandbox_root>/iter1/proposal.md`.

### 1b. The intent to protect (the anti-gaming anchor)
Read the proposal and extract **`<intent>`** = its core research question + headline
contribution, in 2–3 sentences. Show it to the user and have them confirm/correct it. This is
**frozen** for the whole run — the Reviser may never change it (see `roles/Reviser.md`).

### 1c. Passing grade
Record **`<pass_threshold>`** (0–100). *Other*: *"What grade must the proposal reach to pass?
(e.g. 80)"* *Claude Code*: recommend `75 — a solid, well-grounded proposal without demanding
perfection`.

### 1d. Budget & plateau patience
Record **`<budget>`** = max iterations (default 6) and **`<patience>`** = stop after this many
consecutive iterations with no grade improvement (default 2). The loop stops on **pass**, on
`<budget>`, or on `<patience>` plateau.

### 1e. Evaluation depth (the scaling dial)
Record **`<eval_scale>`** — caps how much literature ScholarEval pulls per iteration:

| Preset | Methods · Dimensions examined | Queries each | Papers read (fulltext) | effort |
|---|---|---|---|---|
| **low** | 2 · 2 | 1 | 0 (snippet/abstract only) | low |
| **medium** *(Recommended)* | 4 · 3 | 2 | 2 | medium |
| **high** | 6 · 5 | 3 | 5 | high |

### 1f. Grade weights (frozen for the run)
Record **`grade_weights`** = `w_s · w_c · w_e` (must sum to 1). Default **0.45 · 0.35 · 0.20**
(see `rubric.md`). Recommend the default unless the user has a reason to re-weight.

### 1g. Sandbox location
Record **`<sandbox_root>`** (default `./sandbox/`).

### 1h. Resolve `<lit>` and smoke-test
Set `<lit_py>=python3`; confirm `<lit_py> <skill_dir>/lit_search.py --help` works. If it
fails, stop and report — the loop cannot ground itself without the helper.

### 1i. Semantic Scholar key (the standard `keys.env` onboarding — see `docs/api-keys.md`)
The one key this loop wants is **`S2_API_KEY`** (free): it makes `snippet` + `cite` — the two
ScholarEval-defining retrieval moves — reliable instead of fighting S2's saturated keyless
pool. It is **optional** and the loop degrades (keyless pool → WebSearch/WebFetch), but a key
materially improves grounding, so **walk the user through it; never block on it**, and **never
ask for the secret in chat** — the user pastes it into the file themselves.

Keys live in one shared `keys.env` at the **project root** (nearest `.git` ancestor), reused by
every skill. Follow the four-step flow exactly:

1. **Check what's already there** (another skill may have populated it):
   ```
   <lit> keys
   ```
   `S2_API_KEY.present == true` → record the live tier and skip to 1j.
2. **Ensure the slot exists** (creates `keys.env` at the project root if missing; appends only
   missing keys, never clobbers existing values). Confirm `keys.env` is gitignored first (it is
   in this repo) and add the line if a host project lacks it:
   ```
   <lit_py> <skill_dir>/lit_search.py keys --init
   ```
   It prints the file path.
3. **Ask the user to fill it themselves** so the secret never enters this transcript:
   > "Open `keys.env` (at the project root), paste your free `S2_API_KEY`, and tell me when
   >  you're done. In-session shortcut: `! $EDITOR ./keys.env`. It's optional — say 'skip' and
   >  I'll run on the keyless pool."

   Offer to fill it for them only if they explicitly prefer (then take the value via the file,
   not chat). Real OS env vars (`export S2_API_KEY=…`) also work and win over the file.
4. **Verify and persist.** Re-run `<lit> keys` (network-free, booleans only) and report back:
   whether `S2_API_KEY` is present, what it enables, and exactly what is lost without it
   ("missing → snippet/cite run on the saturated keyless pool; frequent 429s, so ScholarEval
   leans harder on arXiv full-text + WebSearch/WebFetch — everything still runs"). Persist the
   live/degraded tier to `schema.yaml` under `literature_tiers` (the **value never** goes in
   `schema.yaml` — only presence). Do not block on the key.

### 1j. Initialise sandbox
```
<sandbox_root>/
├── schema.yaml          ← all resolved bindings + <intent> + grade_weights (written now)
├── ledger.tsv           ← header only (written now)
├── literature/.cache/   ← lit_search on-disk cache
└── iter1/
    └── proposal.md      ← copy of the input proposal (the baseline)
```
**`ledger.tsv` header** (tab-separated, never commas):
```
iter	grade	pass	soundness	contribution	evidence_quality	top_fix	revision_summary
```

### 1k. Confirm and go
Print every resolved binding, `<intent>`, and the live/degraded literature tier. **Do not
create files or start until the user confirms.**

---

## 2. The loop

`<N>` starts at 1. Iteration 1 **evaluates the unmodified proposal** (the baseline grade —
no revision before it). Each iteration is **evaluate → grade → (stop?) → revise**.

### LOOP until stop:

1. **Evaluate.** Run `roles/ScholarEval.md` (spawn-or-degrade) on
   `<sandbox_root>/iter<N>/proposal.md` with `<eval_scale>` caps and `<lit>`. It writes
   `iter<N>/scholareval.json` (validates against `schemas/scholareval.schema.json`; example in
   `roles/ScholarEval.md`). Every cited snippet must come from a real retrieval — never
   fabricated.

2. **Grade.** As the **Judge** (`roles/Judge.md`), apply `rubric.md` to `scholareval.json`:
   evidence gate → 0–5 per axis → weighted `grade` → hard gates → `pass`, plus ranked `fixes`.
   Write `iter<N>/verdict.json` (validates against `schemas/verdict.schema.json`; example in
   `roles/Judge.md`).

3. **Log.** Append one `ledger.tsv` row (§3).

4. **Stop check.**
   - `verdict.pass == true` → **STOP: passing grade reached.** Report the final proposal
     (`iter<N>/proposal.md`), its grade, and the grade trajectory.
   - `N == <budget>` → **STOP: budget exhausted.** Report the **best-grade** iteration as the
     deliverable, not necessarily the last.
   - grade hasn't improved for `<patience>` consecutive iterations → **STOP: plateau.** Report
     the best iteration and the standing blockers (the unresolved priority-1 fixes).

5. **Revise.** Run `roles/Reviser.md` (spawn-or-degrade) with `verdict.json`, `scholareval.json`,
   `<intent>`, the `<lit>` command, and a small revision search budget (≈`<eval_scale>` searches
   + a couple of reads). It applies the top fixes (one focused batch) — **searching the
   literature for real new support when a fix needs a citation the evaluation didn't already
   surface** — and writes `iter<N+1>/proposal.md` + a short `iter<N+1>/revision_notes.md`.
   **Intent guard:** it may not change `<intent>` or gut a central method to chase the grade.
   **No fabricated citations** — any paper it adds must come from a real retrieval and is
   re-verified by next iteration's evaluation + evidence gate.

6. **`N = N + 1`; go to step 1.**

**Re-evaluate fresh every iteration.** The grade comes only from a *new* ScholarEval pass on
the *revised* proposal — never carried over. A revision that doesn't move the grounded evidence
won't move the grade, by design.

---

## 3. Ledger format

**`ledger.tsv`** (tab-separated, never commas):
```
iter	grade	pass	soundness	contribution	evidence_quality	top_fix	revision_summary
1	58.0	no	3	2	4	add MM-GBSA re-scoring	baseline (no revision)
2	71.0	no	4	3	4	add head-to-head vs [C2] pipeline	added re-scoring + scoped affinity claim
3	82.0	yes	4	4	4	-	reframed contribution around integration + new benchmark
```
The matching `scholareval.json` and `verdict.json` for each iteration live in `iter<N>/`. Do
not commit `ledger.tsv`, `iter*/`, or `literature/` to git — leave them untracked.

---

## 4. Hard constraints (never violate)
- **Never fabricate citations or snippets.** Every `evidence` entry comes from a real
  `lit_search.py` / WebFetch result retrieved that iteration; snippets are verbatim. When a lit
  tool returns `{"error","fallback"}`, fall back to WebSearch/WebFetch — never invent a paper.
- **The rubric is fixed.** The Judge never edits `rubric.md`; the bar stays stable so the
  passing threshold is meaningful.
- **Protect `<intent>`.** The Reviser may strengthen but never replace the core research
  question / headline contribution, and never gut a central method just to lift the grade.
- **Grade through evidence, not prose.** Eloquence earns nothing; grounded support and
  surviving novelty earn the score.
- **One focused revision batch per iteration**, so grade moves are attributable.
- **Report the best iteration**, not the last, when stopping on budget/plateau.
- Do not install packages — `lit_search.py` is stdlib-only. Never print or commit API keys
  (`keys.env` stays gitignored at the project root).
- The sandbox is self-contained — no `../` escapes.

---

## 5. When the loop stops
Always end with: the **deliverable proposal** path, its **grade** and pass/fail, the **grade
trajectory** across iterations (from `ledger.tsv`), and — if it did not pass — the **standing
blockers** (unresolved priority-1 fixes) so the user knows exactly what is between this
proposal and the bar.
