---
name: research-proposal
description: >
  Use when the user has a research proposal (problem + proposed methodology + planned experiments)
  and wants it iteratively strengthened until it clears a passing grade. ScholarEval grades the
  proposal against the literature (Soundness + Contribution), a Judge scores that feedback 0-100 on a
  fixed rubric, and a Reviser rewrites the proposal to fix the worst points without diluting the
  research question; loops until the grade passes or the budget is hit. Not for generating a proposal
  from scratch, and not for running a literature survey on its own.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Research Proposal Loop

The artifact is a **research proposal**; the feedback signal is **ScholarEval** (literature-grounded
Soundness + Contribution) turned into a **0-100 grade** by a **Judge** against the fixed `rubric.md`.
Each iteration **evaluates → grades → revises** until the grade clears `<pass_threshold>` or the
budget runs out.

**North star.** Clearing the threshold is the stopping condition, not the goal. The goal is the
strongest, most novel, genuinely publishable version the proposal can *honestly* become — every
revision should ask "does this make the work more significant and more novel?", not just "does this
patch a flaw?". This is **grounded ambition**: the lift comes from better-justified methods, a
sharper-but-defensible novelty claim, and stronger baselines, all backed by real retrieved evidence.
Overclaiming *lowers* the grade (evidence gate + Contribution axis); it never raises it.

The cast (all in this folder):
- `roles/ScholarEval.md` — the two-module literature-grounded evaluator; emits `scholareval.json`.
- `roles/Judge.md` — grades the feedback → 0-100 + ranked fixes; emits `verdict.json` (decides pass).
- `roles/Reviser.md` — rewrites the proposal to address the fixes (guards the research intent).
- `rubrics/rubric.md` — the **fixed** grading rubric (the Judge never edits it).
- `schemas/scholareval.schema.json`, `schemas/verdict.schema.json` — the two validated outputs.

**Spawn-or-degrade.** On Claude Code, spawn ScholarEval / Reviser as real `Agent` subagents;
otherwise adopt each role inline. You are the orchestrator and the Judge.

## When to use
Use when a written proposal exists and the user wants it pushed past a quality bar with
literature-grounded critique. Default: run the full evaluate→grade→revise loop below. Escape hatch: if
the user only wants the critique (no rewriting), run one ScholarEval + Judge pass and stop. Not for
writing a proposal from a blank page, and not for a standalone literature survey.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it and skip to
the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely value for
each binding and present it as the recommended option; on other hosts ask each as a quoted plain-text
prompt. Then write `loop.run.yaml` (format: `examples/run.example.yaml`) and confirm every value,
`<intent>`, and the live/degraded literature tier before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<proposal_path>` | file with problem + methodology + planned experiments | — | scan for a likely `.md`/`.txt`/`.pdf`; if only prose is pasted, save it to `<sandbox_root>/iter1/proposal.md` |
| `<intent>` | core research question + headline contribution, 2-3 sentences — **frozen**; the Reviser may never change it | — | read the proposal, extract it, have the user confirm |
| `<pass_threshold>` | grade (0-100) the proposal must reach to pass | 75 | a solid, well-grounded proposal without demanding perfection |
| `<budget>` | max iterations | 6 | — |
| `<patience>` | stop after this many consecutive no-improvement iterations | 2 | — |
| `<eval_scale>` | how much literature ScholarEval pulls per iteration (`low`/`medium`/`high`, see below) | `medium` | — |
| `grade_weights` | `soundness · contribution · evidence_quality` (must sum to 1; frozen for the run) | `0.45 · 0.35 · 0.20` | `rubric.md`; recommend default |
| `<sandbox_root>` | where snapshots, ledger, and lit cache live | `./sandbox` | — |

**Evaluation depth dial** (`<eval_scale>` caps per iteration — methods · dimensions examined ·
queries each · papers read full-text):

| preset | methods · dims | queries each | fulltext reads | effort |
|---|---|---|---|---|
| **low** | 2 · 2 | 1 | 0 (snippet/abstract only) | low |
| **medium** *(recommended)* | 4 · 3 | 2 | 2 | medium |
| **high** | 6 · 5 | 3 | 5 | high |

**Literature toolchain.** Paper search goes through the sibling **`literature-search` skill** —
resolve `<lit_skill_dir>` (it installs as a sibling, e.g. `~/.claude/skills/literature-search/`),
`<lit_py> = python3`, and `<lit> = <lit_skill_dir>/tools/lit_search.py`; append
`--cache-dir <sandbox_root>/literature/.cache` after a subcommand to reuse the cache. Confirm
`<lit> --help` works at setup; if the skill is absent, tell the user and either install it
(copy the repo's `loops/literature-search` folder into `~/.claude/skills/`) or degrade all retrieval to WebSearch/WebFetch
(no ranked snippets or citation-graph expansion). The keyless **S2 + arXiv** core
(`search`/`snippet`/`cite`/`fulltext`) needs no setup; a free `S2_API_KEY` makes `snippet`+`cite`
(ScholarEval's two defining moves) reliable.

**API key (optional, never block).** The `literature-search` skill owns the key convention: run
`<lit> keys --init`, then have the user fill the printed `keys.env` themselves and never paste secrets
into chat. Re-run `<lit> keys` to confirm presence and record the tier in `loop.run.yaml`
(`literature_tiers`, presence only). A missing key just degrades to the keyless pool → WebSearch.

**Initialise the sandbox** once bindings are confirmed:
```
<sandbox_root>/
├── loop.run.yaml        ← resolved bindings + <intent> + grade_weights + literature_tiers
├── ledger.tsv           ← header only (see Ledger)
├── literature/.cache/   ← lit_search on-disk cache
└── iter1/proposal.md    ← the input proposal (the baseline)
```

## The loop
`<N>` starts at 1; iteration 1 **evaluates the unmodified proposal** (the baseline grade — no
revision before it). Re-evaluate fresh every iteration: the grade comes only from a *new* ScholarEval
pass on the *revised* proposal, never carried over.

Copy this checklist and tick items off:
- [ ] **Evaluate** — run `roles/ScholarEval.md` (spawn-or-degrade) on `iter<N>/proposal.md` with the `<eval_scale>` caps and `<lit>`; it writes `iter<N>/scholareval.json` (validates against `schemas/scholareval.schema.json`).
- [ ] **Grade** — as the Judge (`roles/Judge.md`) apply `rubrics/rubric.md` to `scholareval.json`: evidence gate → 0-5 per axis → weighted `grade` → hard gates → `pass` + ranked `fixes`; write `iter<N>/verdict.json` (validates against `schemas/verdict.schema.json`).
- [ ] **Log** — append one `ledger.tsv` row (see Ledger).
- [ ] **Stop check** — `verdict.pass == true`, or `N == <budget>`, or grade flat for `<patience>` iterations → stop (see Stops).
- [ ] **Revise** — run `roles/Reviser.md` (spawn-or-degrade) with `verdict.json`, `scholareval.json`, `<intent>`, `<lit>`, and a small revision search budget (≈`<eval_scale>` searches + a couple of reads); it applies one focused fix batch and writes `iter<N+1>/proposal.md` + `iter<N+1>/revision_notes.md`.
- [ ] **`N = N + 1`** and repeat.

Every cited snippet must come from a real retrieval that iteration — never fabricated. When a lit tool
returns `{"error","fallback"}`, fall back to WebSearch/WebFetch; never invent a paper.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text:
```
iter	grade	pass	soundness	contribution	evidence_quality	top_fix	revision_summary
1	58.0	no	3	2	4	add MM-GBSA re-scoring	baseline (no revision)
2	71.0	no	4	3	4	add head-to-head vs [C2] pipeline	added re-scoring + scoped affinity claim
3	82.0	yes	4	4	4	-	reframed contribution around integration + new benchmark
```
The matching `scholareval.json` and `verdict.json` for each iteration live in `iter<N>/`. Report the
**best**-grade iteration when stopping on budget/plateau, not necessarily the last. Leave `ledger.tsv`,
`iter*/`, and `literature/` untracked.

## Constraints
- **Never fabricate citations or snippets** — every `evidence` entry comes from a real `<lit>`/WebFetch
  result retrieved that iteration, verbatim; the evidence gate exists to catch fabrication.
- **The rubric is fixed** — the Judge never edits `rubrics/rubric.md`, so the passing threshold stays
  meaningful across iterations.
- **Protect `<intent>`** — the Reviser may strengthen but never replace the core research question or
  headline contribution, and never gut a central method just to lift the grade.
- **Grade through evidence, not prose** — eloquence earns nothing; grounded support and surviving
  novelty earn the score.
- **One focused revision batch per iteration**, so each grade move is attributable.
- **No installs** — the sibling `literature-search` skill is stdlib-only; never print or commit API keys
  (`keys.env` stays gitignored at the project root). The sandbox is self-contained — no `../` escapes.

## Stops
The loop stops on the first of:
- **Pass** — `verdict.pass == true`. Report the final proposal (`iter<N>/proposal.md`), its grade, and
  the grade trajectory.
- **Budget** — `N == <budget>`. Report the best-grade iteration as the deliverable.
- **Plateau** — grade hasn't improved for `<patience>` consecutive iterations. Report the best
  iteration and the standing priority-1 fixes.

Always end with the deliverable proposal path, its grade and pass/fail, the grade trajectory from
`ledger.tsv`, and — if it did not pass — the standing blockers between this proposal and the bar.
