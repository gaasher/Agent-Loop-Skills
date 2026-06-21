---
name: scientificWriterLoop
description: >
  Use when the user has a dataset and a draft of a piece of scientific writing and wants it
  iteratively improved until it clears a quality bar. Each iteration, five specialist judges
  (figures, scientific content, style, formatting, code) critique the draft; a single fresh
  peer_reviewer independently grades it on those same five axes (1-5 each → a percentage); and
  a scientific_writer revises the prose, figures, and code — grounding new citations in S2 +
  arXiv. Loops until the peer-review score clears the user's threshold. All work happens on
  copies inside a sandbox; the user's originals are never touched.
metadata:
  version: "0.1.0"
---

# Scientific Writer Loop

Artifact = a **piece of scientific writing** (draft + its dataset + figures + optional code).
Feedback = **five specialist judges** producing concrete findings, and a **peer_reviewer**
turning the paper into a graded score. The loop **critiques → grades → revises** until the
score clears `<pass_threshold>`.

The cast and files (all in this folder):
- `roles/figures_judge.md`, `roles/scientific_judge.md`, `roles/style_judge.md`,
  `roles/formatting_judge.md`, `roles/code_reviewer.md` — the five critics. Each emits the
  shared `schemas/finding.schema.json`.
- `roles/peer_reviewer.md` — the summative grader (its own honesty rules); emits
  `schemas/peer_review.schema.json`.
- `roles/scientific_writer.md` — the reviser; uses the lit tool.
- `schemas/config.schema.json` — the resolved-bindings contract.
- `tools/lit_search.py` + `tools/lit/` — the vendored **S2 + arXiv** retrieval backend.

Spawn-or-degrade: on Claude Code, spawn the judges / peer_reviewer / writer as real `Agent`
subagents (the five judges in parallel); otherwise adopt each role inline. **You are the
orchestrator.**

## Why the grader is built the way it is (the honesty problem)

The peer_reviewer grades on the **same five axes** the judges critique — which invites echoing,
inflation under loop-termination pressure, and a writer that games the rubric. `roles/peer_reviewer.md`
counters this: it (1) grades **independently** and re-derives each axis before reading the
critiques, (2) **verifies** a sample of numbers/citations itself rather than trusting "it's
fixed", (3) must surface **issues the judges missed**, (4) holds a **fixed, anchored,
reproducible** bar with **no credit for effort or elapsed iterations**, (5) applies **hard
gates** (a confirmed block fails the paper regardless of the average), and (6) runs a
**substance check** against surface compliance. The *writer* optimizes the judges' concrete
findings; the *grader* judges holistically — so "address every finding" does not mechanically
buy a pass.

---

## 0. The literature toolchain (read once)

All literature access goes through `tools/lit_search.py` — stdlib-only, no installs. Resolve
once and reuse:
- **`<skill_dir>`** — this folder. **`<lit_py>`** — `python3` (any ≥3.9).
- **`<lit>`** — `<lit_py> <skill_dir>/tools/lit_search.py --cache-dir <sandbox_root>/literature/.cache`

Subcommands (print JSON; on failure print `{"error","fallback"}` → fall back to WebSearch/WebFetch):
`search` (discover), `snippet` (pinpoint a passage), `cite <paperId> --direction
references|citations|recommend` (citation graph), `fulltext <arxivId>` (read a paper),
`keys [--init]`. This is the **S2 + arXiv** stack; `S2_API_KEY` is free and recommended.
Used by `scientific_writer` (ground new citations) and `peer_reviewer` (verify citations).

---

## 1. Resolve bindings (setup — do this once)

**MANDATORY INTERACTIVE SETUP. Ask every question and wait for the answer. Do NOT infer or
auto-apply. If you skip any, you are doing it wrong.** Record into `schemas/config.schema.json`.

### 1.0 Detect host
Check whether `AskUserQuestion` is available. **Yes → Claude Code path** (infer + recommend);
**No → plain-text path** (quoted prompts). Record **`<host>`**.

### 1a. The draft & dataset
Record **`<draft_path>`** (the writing) and **`<dataset_paths>`** (the data the claims/figures
derive from — needed to verify numbers). *Claude Code*: scan for likely files and recommend.

### 1b. Figures & code
Record **`<figures_dir>`** (images the draft references) and **`<code_paths>`** (scripts that
produce plots/results). Then ask for a **`<plot_command>`** that regenerates figures/results
(e.g. `python3 code/make_figures.py`). If there is no such code, leave `code_paths` empty — the
**code axis is dropped** (n_axes = 4) and `code_reviewer` is not spawned. If there is code but
no command, figures/code are **edit-only** (no execution, flagged "needs regeneration").

### 1c. Style targets
Record **`<citation_style>`** (`APA`|`MLA`), optional **`<target_venue>`**, and optional
**`<length_limits>`** (abstract/paper word counts).

### 1d. Passing bar, budget, patience
Record **`<pass_threshold>`** (0–100; e.g. 85), **`<budget>`** (max iterations, default 6), and
**`<patience>`** (stop after this many no-improvement iterations, default 2).

### 1e. Sandbox location
Record **`<sandbox_root>`** (default `./sandbox/`). **The loop only ever reads the originals and
writes copies under here — it never edits the user's files in place.**

### 1f. Literature key (the standard `keys.env` onboarding — see `docs/api-keys.md`)
Smoke-test `<lit_py> <skill_dir>/tools/lit_search.py --help`. Then run the four-step flow:
`<lit> keys` (check) → `tools/lit_search.py keys --init` (append the gitignored `keys.env` slot
at the project root) → ask the user to paste their free `S2_API_KEY` into the file themselves
(`! $EDITOR ./keys.env`; "skip" is fine) → re-run `<lit> keys`, report presence + what's lost
without it, and persist the tier (booleans only) to `config.yaml` under `literature_tiers`. The
secret never enters chat; OS env vars win; never block on the key.

### 1g. Initialise the sandbox (copy in the originals)
```
<sandbox_root>/
├── config.yaml          ← resolved bindings (written now)
├── ledger.tsv           ← header only (written now)
├── literature/.cache/   ← lit_search cache
└── iter1/
    ├── draft.md         ← COPY of <draft_path>
    ├── figures/         ← COPY of <figures_dir>
    └── code/            ← COPY of <code_paths>     (omit if no code)
```
**`ledger.tsv` header** (tab-separated, never commas):
```
iter	overall_score	pass	figures	scientific	style	formatting	code	top_fix	revision_summary
```
(Use `-` in the `code` column when the code axis is absent.)

### 1h. Confirm and go
Print every resolved binding, the live/degraded literature tier, and which axes are active
(4 vs 5). **Do not create files or start until the user confirms.**

---

## 2. The loop

`<N>` starts at 1. Iteration 1 critiques and grades the **unmodified** draft (the baseline — no
revision before it). Each iteration: **critique → grade → (stop?) → revise**.

### LOOP until pass / budget / plateau:

1. **Critique.** Spawn the active judges **in parallel** (spawn-or-degrade), each over the
   `iter<N>/` working copies + dataset. Each writes `iter<N>/critiques/<reviewer>.json`
   (validates against `schemas/finding.schema.json`). Skip `code_reviewer` when no code.
2. **Grade.** Spawn **one fresh** `peer_reviewer` (`roles/peer_reviewer.md`) → it grades
   independently (own read first, then reconcile with critiques; spot-checks; surfaces missed
   issues), writes `iter<N>/peer_review.json` (validates against `schemas/peer_review.schema.json`):
   1–5 per active axis, `overall_score = 100 × Σscore / (5 × n_axes)`, hard gates → `pass`.
3. **Log.** Append the `ledger.tsv` row.
4. **Stop check.**
   - `peer_review.pass == true` → **STOP: bar reached.** Report the deliverable
     (`iter<N>/` artifacts), the score, and the trajectory.
   - `N == <budget>` → **STOP: budget exhausted.** Report the **best-scoring** iteration.
   - `overall_score` hasn't improved for `<patience>` iterations → **STOP: plateau.** Report the
     best iteration + the standing `gate_failures`/`must_fix` blockers.
5. **Revise.** Spawn `scientific_writer` (`roles/scientific_writer.md`) with the critiques, the
   peer review, `<lit>`, `<plot_command>`, `<citation_style>`, and `<intent>`. It fixes
   block/gate items first, fixes code → regenerates figures (running the copied `<plot_command>`
   **inside the sandbox**) → updates prose, grounds new citations via `<lit>`, and writes
   `iter<N+1>/{draft.md,figures/,code/}` + `iter<N+1>/revision_notes.md`. **Intent guard:** it
   may not change the core finding, hollow out the paper, or fabricate anything.
6. **`N = N + 1`; go to step 1.**

**Re-grade fresh every iteration** — the score comes only from a new peer review of the revised
paper, never carried over. Surface-only changes won't move it.

---

## 3. Ledger format

```
iter	overall_score	pass	figures	scientific	style	formatting	code	top_fix	revision_summary
1	28.0	no	1	1	2	2	1	fix make_figures sort bug	baseline (no revision)
2	61.0	no	3	3	3	3	4	report honest r, de-causalize	fixed bug+claims; relabeled fig1
3	88.0	yes	4	5	4	4	5	-	unified APA; trimmed abstract; balanced sleep claim
```
The per-iteration `critiques/*.json`, `peer_review.json`, and `revision_notes.md` live in
`iter<N>/`. Do not commit the sandbox to git — leave it untracked.

---

## 4. Hard constraints (never violate)
- **Never edit or run anything outside `<sandbox_root>`.** Read the user's originals once at
  setup, copy them in, and work only on the copies. Only run a command that lives in the
  sandbox (the `<plot_command>` is copied in with the code).
- **Never fabricate** data, numbers, figures, or citations. New citations come from real
  `<lit>` / WebFetch retrievals, quoted verbatim. On `{"error","fallback"}`, use WebSearch/WebFetch.
- **The grading bar is fixed and reproducible.** The peer_reviewer never relaxes anchors to let
  the loop finish; a confirmed hard gate fails the paper regardless of the average.
- **Protect `<intent>`.** The writer strengthens the *same* finding; it never changes the core
  result or deletes a real finding to dodge a critique.
- **One coherent revision batch per iteration**, blocks/gates first, so score moves are
  attributable. **Report the best iteration**, not the last, on budget/plateau.
- Do not install packages (`lit_search.py` is stdlib-only). Never print or commit API keys.

---

## 5. When the loop stops
End with: the **deliverable** (`iter<N>/` path), its `overall_score` and pass/fail, the
per-axis scores, the **score trajectory** from `ledger.tsv`, and — if it did not pass — the
**standing blockers** (`gate_failures` + open `must_fix`) so the user knows exactly what stands
between the paper and the bar.
