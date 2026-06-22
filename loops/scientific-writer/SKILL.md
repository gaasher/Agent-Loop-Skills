---
name: scientific-writer
description: >
  Use when the user has a scientific draft (with its dataset, figures, and optional analysis code)
  and wants it iteratively revised until it clears a quality bar. Five specialist judges (figures,
  scientific content, style, formatting, code) critique the draft; a fresh, independent peer_reviewer
  grades it on those same axes (1-5 each → a percentage) with honesty guardrails; a scientific_writer
  revises prose, figures, and code — regenerating figures by running the user's plot command — until
  the peer-review score clears the threshold or the budget is hit. Not for writing a paper from a
  blank page, and not for a standalone literature survey.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Scientific Writer Loop

The artifact is a **piece of scientific writing** (draft + its dataset + figures + optional code).
Each iteration **critiques → grades → revises**: five specialist judges produce concrete findings,
an independent **peer_reviewer** turns the paper into a graded 0-100 score on the same axes, and a
**scientific_writer** fixes the prose, figures, and code — running the user's `<plot_command>` to
regenerate figures. The loop runs until the score clears `<pass_threshold>` or the budget is hit. All
work happens on copies inside a sandbox; the user's originals are never touched.

The cast (all in this folder):
- `roles/figures_judge.md`, `roles/scientific_judge.md`, `roles/style_judge.md`,
  `roles/formatting_judge.md`, `roles/code_reviewer.md` — the five critics; each emits the shared
  `schemas/finding.schema.json`.
- `roles/peer_reviewer.md` — the summative grader (its own honesty rules); emits
  `schemas/peer_review.schema.json` and decides `pass`.
- `roles/scientific_writer.md` — the reviser; fixes code → regenerates figures → updates prose.
- `schemas/finding.schema.json`, `schemas/peer_review.schema.json` — the two validated outputs.

**Spawn-or-degrade.** On Claude Code, spawn the active judges as real `Agent` subagents **in
parallel**, then one fresh `peer_reviewer`, then the `scientific_writer`; otherwise adopt each role
inline. You are the orchestrator.

## Why the grader is built this way (the honesty problem)

The peer_reviewer grades on the **same axes** the judges critique — which invites echoing, inflation
under loop-termination pressure, and a writer that games the rubric. `roles/peer_reviewer.md`
counters this: it (1) grades **independently**, re-deriving each axis from the paper + dataset before
reading the critiques, (2) **verifies** a sample of numbers/citations itself rather than trusting
"it's fixed", (3) must surface **issues the judges missed**, (4) holds a **fixed, anchored,
reproducible** bar with **no credit for effort or elapsed iterations**, (5) applies **hard gates** (a
confirmed block fails the paper regardless of the average), and (6) runs a **substance check** against
surface compliance. The *writer* optimizes the judges' concrete findings; the *grader* judges
holistically — so "address every finding" does not mechanically buy a pass.

## When to use
Use when a written scientific draft exists and the user wants it pushed past a quality bar with
multi-judge critique and an independent peer-review grade. Default: run the full critique→grade→revise
loop below. Escape hatch: if the user only wants the critique (no rewriting), run one round of judges
+ peer_reviewer and stop. Not for writing a paper from a blank page, and not for a standalone
literature survey.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other
hosts ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format:
`examples/run.example.yaml`) and confirm every value — including which axes are active (4 vs 5) and the
live/degraded literature tier — before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<draft_path>` | the draft to improve (markdown/text/tex) | — | scan the working dir for a likely draft |
| `<dataset_paths>` | data file(s) the claims/figures derive from — used to verify numbers | — | scan for data files near the draft |
| `<figures_dir>` | directory of figure images the draft references | — | scan near the draft; may be null |
| `<code_paths>` | source files that produce plots/results; **empty → code axis dropped** (n_axes=4, no `code_reviewer`) | — | scan for plotting/analysis scripts |
| `<plot_command>` | command that regenerates figures/results from the code; **null → figures/code are edit-only** (flagged "needs regeneration") | — | `pyproject.toml`/`.venv`/README; e.g. `python3 code/make_figures.py` |
| `<citation_style>` | the single style the formatting_judge enforces (`APA`\|`MLA`) | `APA` | ask the user |
| `<target_venue>` | optional venue whose style/length norms apply | — | ask the user |
| `<length_limits>` | optional abstract/paper word-count targets | — | ask the user |
| `<intent>` | the paper's core finding/contribution, 1-2 sentences — **frozen**; the writer may never change it | — | read the draft, extract it, confirm with the user |
| `<pass_threshold>` | overall_score (0-100) the peer_reviewer must reach (and no hard gate) to stop | 85 | a solid paper without demanding perfection |
| `<budget>` | max iterations | 6 | — |
| `<patience>` | stop after this many consecutive no-improvement iterations | 2 | — |
| `<sandbox_root>` | where working copies, critiques, reviews, and the ledger live | `./sandbox` | — |

**Literature toolchain.** Citation grounding (writer) and verification (scientific_judge,
peer_reviewer) go through the sibling **`literature-search` skill** — resolve `<lit_skill_dir>` (it
installs as a sibling, e.g. `~/.claude/skills/literature-search/`), `<lit_py> = python3`, and
`<lit> = <lit_skill_dir>/tools/lit_search.py`; append `--cache-dir
<sandbox_root>/literature/.cache` after a subcommand to reuse the cache. Confirm `<lit> --help` works
at setup; if the skill is absent, tell the user and either install it (copy the repo's
`loops/literature-search` folder into `~/.claude/skills/`) or degrade all retrieval to
WebSearch/WebFetch. The keyless **S2 + arXiv** core works with no setup; a free `S2_API_KEY` makes
`snippet`/`cite` reliable — run `<lit> keys --init`, have the user fill the printed `keys.env`
themselves, and **never paste secrets into chat**. Record the tier (presence only) in `loop.run.yaml`.

**Environment.** The writer regenerates figures by running the user's `<plot_command>` **in the user's
own environment** — that code may need third-party deps (matplotlib, pandas, …), so the skill **ships
none** and never installs them; it shells out to the user's command and reads the regenerated outputs.
Helper code the skill writes stays stdlib-only. `tools/lit_search.py` (in the sibling skill) is
stdlib-only too.

**Initialise the sandbox** once bindings are confirmed (copy in the originals; never edit them in place):
```
<sandbox_root>/
├── loop.run.yaml        ← resolved bindings + <intent> + literature_tiers
├── ledger.tsv           ← header only (see Ledger)
├── literature/.cache/   ← lit_search on-disk cache
└── iter1/
    ├── draft.md         ← COPY of <draft_path>
    ├── figures/         ← COPY of <figures_dir>
    └── code/            ← COPY of <code_paths>   (omit if no code)
```

## The loop
`<N>` starts at 1; iteration 1 critiques and grades the **unmodified** draft (the baseline — no
revision before it). Re-grade fresh every iteration: the score comes only from a *new* peer review of
the *revised* paper, never carried over. Surface-only changes won't move it.

Copy this checklist and tick items off:
- [ ] **Critique** — spawn the active judges **in parallel** (spawn-or-degrade), each over the `iter<N>/` working copies + dataset; each writes `iter<N>/critiques/<reviewer>.json` (validates against `schemas/finding.schema.json`). Skip `code_reviewer` when no code.
- [ ] **Grade** — spawn **one fresh** `peer_reviewer` (`roles/peer_reviewer.md`): it grades independently (own read first, then reconcile with the critiques; spot-checks numbers/citations; surfaces missed issues), writes `iter<N>/peer_review.json` (validates against `schemas/peer_review.schema.json`): 1-5 per active axis, `overall_score = 100 × Σscore / (5 × n_axes)`, hard gates → `pass`.
- [ ] **Log** — append one `ledger.tsv` row (see Ledger).
- [ ] **Stop check** — `peer_review.pass == true`, or `N == <budget>`, or `overall_score` flat for `<patience>` iterations → stop (see Stops).
- [ ] **Revise** — spawn `scientific_writer` (`roles/scientific_writer.md`) with the critiques, the peer review, `<lit>`, `<plot_command>`, `<citation_style>`, and `<intent>`. It fixes block/gate items first, fixes code → regenerates figures (running the copied `<plot_command>` **inside the sandbox**) → updates prose, grounds new citations via `<lit>`, and writes `iter<N+1>/{draft.md,figures/,code/}` + `iter<N+1>/revision_notes.md`.
- [ ] **`N = N + 1`** and repeat.

A judge `finding` and a `peer_review` look like (abridged; full shapes in `schemas/`):
```json
{"reviewer": "code_reviewer", "iteration": 1, "overall": "block",
 "summary": "Block: make_figures.py sorts the two columns independently, fabricating r=0.98 (true r≈0.62).",
 "findings": [{"urgency": "must_fix", "action_type": "replace", "area": "make_figures:broken-pairing",
   "finding": "xs=sorted(study); ys=sorted(score) destroys per-row pairing; r inflated to 0.98 (real ≈0.62).",
   "proposed_action": "Correlate the paired arrays; re-render Fig 1; update r everywhere.",
   "target_artifact": "iter1/code/make_figures.py", "evidence": "code/make_figures.py:~70; paired r=0.62"}]}
```
```json
{"iteration": 1,
 "axes": {"figures": {"score": 1, "justification": "Fig 1 plots bug-sorted data; numbers != data.", "blocking_issues": ["fig r=0.98 != paired r=0.62"]},
          "scientific": {"score": 1, "justification": "Causal claim from one correlation; r unreproducible."},
          "style": {"score": 2, "justification": "Promotional, AI-flavored prose."},
          "formatting": {"score": 2, "justification": "Mixed APA/MLA; Results before Methods."},
          "code": {"score": 1, "justification": "Independent column sort fabricates r=0.98."}},
 "overall_score": 28.0, "pass": false,
 "gate_failures": ["make_figures.py sort bug makes r=0.98 an artifact (true 0.62)"],
 "issues_judges_missed": ["Methods omits the test used and n."],
 "spotchecks": [{"target": "paired Pearson r", "method": "recomputed from data", "result": "refuted"}],
 "substance_check": "Baseline iteration — nothing revised yet."}
```

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text:
```
iter	overall_score	pass	figures	scientific	style	formatting	code	top_fix	revision_summary
1	28.0	no	1	1	2	2	1	fix make_figures sort bug	baseline (no revision)
2	61.0	no	3	3	3	3	4	report honest r, de-causalize	fixed bug+claims; relabeled fig1
3	88.0	yes	4	5	4	4	5	-	unified APA; trimmed abstract; balanced sleep claim
```
Use `-` in the `code` column when the code axis is absent. The per-iteration `critiques/*.json`,
`peer_review.json`, and `revision_notes.md` live in `iter<N>/`. Report the **best**-scoring iteration
when stopping on budget/plateau, not necessarily the last. Leave the sandbox untracked.

## Constraints
- **Never edit or run anything outside `<sandbox_root>`** — read the originals once at setup, copy
  them in, and work only on the copies; the `<plot_command>` is copied in and run from the sandbox.
- **Never fabricate** data, numbers, figures, or citations — new citations come from real `<lit>` /
  WebFetch retrievals, quoted verbatim; on `{"error","fallback"}`, fall back to WebSearch/WebFetch.
- **The grading bar is fixed and reproducible** — the peer_reviewer never relaxes anchors to let the
  loop finish; a confirmed hard gate fails the paper regardless of the average.
- **Protect `<intent>`** — the writer strengthens the *same* finding; it never changes the core result
  or deletes a real finding to dodge a critique, because removing a result to raise a score is gaming.
- **One coherent revision batch per iteration**, blocks/gates first, so score moves are attributable.
- **No installs** — the skill ships no deps; `<plot_command>` runs in the user's env, helper code is
  stdlib-only. Never print or commit API keys (`keys.env` stays gitignored).

## Stops
The loop stops on the first of:
- **Pass** — `peer_review.pass == true`. Report the deliverable (`iter<N>/` artifacts), the score, and
  the trajectory.
- **Budget** — `N == <budget>`. Report the best-scoring iteration as the deliverable.
- **Plateau** — `overall_score` flat for `<patience>` iterations. Report the best iteration + the
  standing `gate_failures`/`must_fix` blockers.

Always end with the deliverable (`iter<N>/` path), its `overall_score` and pass/fail, the per-axis
scores, the score trajectory from `ledger.tsv`, and — if it did not pass — the standing blockers
(`gate_failures` + open `must_fix`) between the paper and the bar.
