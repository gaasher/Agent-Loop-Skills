---
name: scientific-figure
description: >
  Use when the user has scientific data (or a prompt alluding to scientific data) and wants a
  publication-quality figure made from it. A generator drafts and renders a figure that lands a frozen
  communication goal; an adversarial critic critiques it hard and grades it 1-5 per axis against a fixed
  rubric (message, aesthetic, clarity, integrity, and a conditional domain-completeness axis), aggregates
  to 0-100, and decides pass; the generator revises against the critic's findings until the grade clears
  a threshold or the budget is hit. Both roles may consult the literature (Semantic Scholar + arXiv) to
  verify domain content (e.g. a pathway figure's gene set, or a benchmark's reported numbers), and
  conform to / grade against a named journal's figure spec fetched via web search. Not for writing a
  paper or analyzing a dataset, and not for editing an existing finished image — this renders a figure
  from data/brief and iterates on it.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Scientific Figure Loop

The artifact is a **scientific figure** (the rendered image + the `plot.py` that produces it). Each
iteration **generates → critiques+grades**: a **generator** authors a rendering script and renders the
figure to land the frozen `<goals>` message; an adversarial **critic** grades it 0-100 against the fixed
`rubrics/rubric.md` and decides `pass`; the generator then revises against the critic's concrete
`findings`. The loop runs until the grade clears `<pass_threshold>` or the budget is hit. All work
happens on copies inside a sandbox; the user's data is copied in read-only and never edited.

The cast (all in this folder):
- `roles/generator.md` — drafts/revises `plot.py`, renders `figure.png` by running `<render_cmd>`,
  optionally grounds domain content via `<lit>`; writes `generation_notes.md`.
- `roles/critic.md` — the adversarial grader: re-derives each rubric axis independently, spot-checks the
  figure's numbers against the data, optionally lit-checks domain completeness, and emits
  `schemas/critique.schema.json` (the grade + `pass` + executable findings).
- `rubrics/rubric.md` — the **fixed** grading rubric (the critic never edits it).
- `schemas/critique.schema.json` — the one validated output.

**Spawn-or-degrade.** On Claude Code, spawn the `generator` then the `critic` as real `Agent` subagents
(sequential — the critic needs the generator's figure); otherwise adopt each role inline. You are the
orchestrator.

## Why the critic grades itself (the honesty problem)

The critic both critiques **and** grades, which under loop-termination pressure invites inflation and a
generator that games the rubric. `roles/critic.md` + `rubrics/rubric.md` counter this: the critic (1)
applies a **fixed** rubric it never edits, (2) **re-derives** each axis from the rendered figure + data +
frozen `<goals>` rather than echoing the generator, (3) **recomputes** a sample of the figure's numbers
itself instead of trusting "it's fixed", (4) holds a **fixed, anchored** bar with **no credit for effort
or elapsed iterations**, and (5) applies **hard gates** (a figure value that contradicts the data, a
misleading axis, or fabricated data presented as real fails the figure regardless of the average). The
generator optimizes the concrete `findings`; the critic grades holistically against the frozen goal — so
"address every finding" does not mechanically buy a pass. Because the two are separate agents, the critic
never just rubber-stamps the generator's intent.

## When to use
Use when scientific data (or a prompt describing it) exists and the user wants a polished figure pushed
past a quality bar with adversarial critique and a graded rubric. Default: run the full
generate→critique loop below. Escape hatch: if the user only wants one figure + a critique (no
iterating), run one generate + critic pass and stop. Not for writing a paper or doing the analysis, and
not for retouching an already-final image.

## Setup
**Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it, confirm the
values in one line, and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is
available) infer a likely value for each binding and present it as the recommended option; on other hosts
ask each as a quoted plain-text prompt. Then write `loop.run.yaml` (format: `examples/run.example.yaml`)
and confirm every value — including the distilled `<goals>`, whether a journal spec applies, and the
live/degraded literature tier — before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<brief>` | the prompt describing the figure to create + the message/claim it must communicate (and, if data exists, what the data represents) | — | the user's request; if pasted as prose, save to `<sandbox_root>/brief.md` |
| `<data_paths>` | data file(s) the figure visualizes (CSV/TSV/parquet/JSON…); **empty → an illustrative/schematic figure** (the integrity axis then checks internal consistency, not data fidelity) | — | scan the working dir near the request; may be null |
| `<goals>` | the figure's communication objective(s), 1-3 bullets — **frozen**; the critic grades against these and the generator may never abandon them | — | **distill from `<brief>` at setup**, confirm with the user in one line |
| `<render_cmd>` | command/interpreter that runs the plot script the generator writes (it appends `iter<N>/plot.py`), in the user's env — the skill ships no plotting deps, the same contract as scientific-writer's `<plot_command>` | `python3` | `pyproject.toml`/`.venv`/README; e.g. `uv run python` or a venv python |
| `<style>` | optional aesthetic/style guide **or a named target journal/venue** — when a journal is named, its figure spec is fetched at setup (see below) and both roles conform to / grade against it | — | ask the user; check `<brief>` for a venue |
| `<pass_threshold>` | overall_score (0-100) the critic must reach (and no hard gate) to stop | 85 | a polished, publication-ready figure without demanding perfection |
| `<budget>` | max iterations | 6 | — |
| `<patience>` | stop after this many consecutive no-improvement iterations | 2 | — |
| `<sandbox_root>` | where the plot scripts, figures, critiques, and the ledger live | `./sandbox` | — |

The **domain axis is not a binding** — the critic auto-detects whether the figure makes an external
domain claim (a named pathway, gene set, canonical benchmark, taxonomy, mechanism, or a literature-
established number) and activates the domain axis itself; no user toggle.

**Literature toolchain (optional, S2 + arXiv only).** Domain grounding goes through the sibling
**`literature-search` skill** — resolve `<lit_skill_dir>` (it installs as a sibling, e.g.
`~/.claude/skills/literature-search/`), `<lit_py> = python3`, and `<lit> =
<lit_skill_dir>/tools/lit_search.py`; append `--cache-dir <sandbox_root>/literature/.cache` after a
subcommand to reuse the cache. Use **only the keyless S2 + arXiv core** (`<lit> search` default
`--source s2`, `snippet`, `cite`, `fulltext`); **do not** use `--source openalex|both`, `ask`, or
`bgpt`. Confirm `<lit> --help` works at setup; if the skill is absent, degrade all retrieval to
WebSearch/WebFetch. Record the tier (presence only) in `loop.run.yaml`.

**Reuse what you've already pulled — don't re-query every iteration.** Every retrieval is cached under
`--cache-dir <sandbox_root>/literature/.cache`, and each role appends the facts it establishes (claim →
number/element → source) to `<sandbox_root>/literature/sources.md`. Both roles **consult that record (and
the cache) first** and only fetch papers/snippets not already on hand; a value a prior iteration already
verified is re-checked by re-reading its recorded source, not by re-searching from scratch. The point of
the literature step is correctness, not call volume — once a paper is pulled, work from it.

**Journal style sheets (separate path, via web search).** When `<style>` names a journal/venue, fetch its
**figure guidelines once at setup via WebSearch/WebFetch** → `<sandbox_root>/style/journal_spec.md`
(column width in mm, minimum font size, fonts, line weights, color mode, panel-label convention, file
requirements). Both roles read this **single cached spec** — the generator conforms, the critic anchors
its aesthetic/clarity axes to it — so the two never grade against divergent specs. This is **distinct from
`<lit>`**: web search finds the journal's *style spec*; `<lit>` (S2/arXiv) checks *domain content*.

**Environment.** The generator renders figures by running `<render_cmd>` **in the user's own
environment** — that code needs third-party deps (matplotlib, pandas, …), so the skill **ships none** and
never installs them; it shells out to `<render_cmd>` and reads the rendered `figure.png`. PNG is rendered
so the critic can view the image (an SVG would be read as XML). The deliverable is `figure.png` **plus its
`plot.py`** — the reproducible source the user re-renders to any vector format. Any helper code the skill
writes stays stdlib-only.

**Initialise the sandbox** once bindings are confirmed (copy the data in read-only; never edit originals):
```
<sandbox_root>/
├── loop.run.yaml        ← resolved bindings + <goals> + literature_tiers
├── brief.md             ← <brief> (if pasted as prose)
├── ledger.tsv           ← header only (see Ledger)
├── data/                ← read-only COPY of <data_paths>   (omit if no data)
├── style/journal_spec.md ← fetched journal figure spec     (omit if no journal named)
├── literature/.cache/   ← lit_search on-disk cache
└── iter1/               ← created by the generator
    ├── plot.py
    ├── figure.png
    ├── generation_notes.md
    └── critique.json
```

## The loop
`<N>` starts at 1. Unlike loops that grade an existing baseline, **the generator runs first** every
iteration (there is no input figure to critique) — iteration 1 drafts from scratch, iterations 2+ revise.
Re-grade fresh every iteration: the score comes only from a *new* critique of the *current* figure, never
carried over. Surface-only changes won't move it.

Copy this checklist and tick items off:
- [ ] **Generate** — spawn `generator` (`roles/generator.md`) with `<brief>`, `<data_paths>`, `<goals>`,
  `<style>` (+ `style/journal_spec.md`), `<render_cmd>`, `<lit>`, and — on iter 2+ — `iter<N-1>/critique.json`.
  It writes/edits `iter<N>/plot.py`, runs `<render_cmd> iter<N>/plot.py` **inside the sandbox** to render
  `iter<N>/figure.png`, grounds any domain content via `<lit>`, and writes `iter<N>/generation_notes.md`.
- [ ] **Critique + grade** — spawn **one fresh** `critic` (`roles/critic.md`) over `iter<N>/figure.png` +
  the data + `<goals>`, applying `rubrics/rubric.md`: it re-derives each axis 1-5 independently,
  spot-checks the figure's numbers against the data, optionally lit-checks domain completeness, computes
  `overall_score = 100 × Σscore / (5 × n_axes)`, applies hard gates → `pass`, and writes
  `iter<N>/critique.json` (validates against `schemas/critique.schema.json`).
- [ ] **Log** — append one `ledger.tsv` row (see Ledger).
- [ ] **Stop check** — `critique.pass == true`, or `N == <budget>`, or `overall_score` flat for
  `<patience>` iterations → stop (see Stops).
- [ ] **`N = N + 1`** and repeat (back to Generate, which now revises against the critique).

A `critique` looks like (abridged; full shape in `schemas/critique.schema.json`):
```json
{"iteration": 2, "summary": "Needs revision: honest now, but the MAPK panel omits ERK and the y-axis lacks units.",
 "axes": {"message": {"score": 4, "justification": "Up-regulation reads clearly."},
          "aesthetic": {"score": 3, "justification": "Palette not colorblind-safe (red/green)."},
          "clarity": {"score": 4, "justification": "Y-axis missing units."},
          "integrity": {"score": 4, "justification": "Bar heights match data/levels.csv."},
          "domain": {"score": 3, "justification": "MAPK cascade missing ERK node."}},
 "overall_score": 72.0, "pass": false, "gate_failures": [],
 "spotchecks": [{"target": "group-B bar = 2.4", "method": "recomputed from data/levels.csv", "result": "confirmed"}],
 "findings": [{"urgency": "must_fix", "action_type": "add", "area": "domain:incomplete",
   "finding": "MAPK cascade panel omits ERK1/2 downstream of MEK.", "proposed_action": "Add ERK node + MEK→ERK edge.",
   "target_artifact": "iter2/plot.py", "evidence": "lit snippet: canonical MAPK = RAF→MEK→ERK"}]}
```

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text:
```
iter	overall_score	pass	message	aesthetic	clarity	integrity	domain	top_fix	generation_summary
1	52.0	no	3	2	2	4	-	label axes + fix palette	baseline draft
2	74.0	no	4	3	4	4	3	add missing MAPK nodes (lit)	relabeled; colorblind palette; +ERK/MEK
3	88.0	yes	5	4	5	5	4	-	rebalanced panels; legend off-data
```
Use `-` in the `domain` column when the domain axis is inactive (n_axes=4). The per-iteration
`critique.json` and `generation_notes.md` live in `iter<N>/`. Report the **best**-scoring iteration when
stopping on budget/plateau, not necessarily the last. Leave the sandbox untracked.

## Constraints
- **Never edit or run anything outside `<sandbox_root>`** — data is copied in read-only at setup; the
  generator's `plot.py` and `<render_cmd>` run from the sandbox; no `../` escapes.
- **Never fabricate** data, numbers, or domain elements. A figure presented as real data must render from
  `<data_paths>`; with no data, the figure must read as clearly illustrative/schematic, not a fake data
  plot. Domain content (genes, nodes, baselines, reported numbers) added from `<lit>` comes from a real
  retrieval that iteration, never invented.
- **The grading bar is fixed and reproducible** — the critic never relaxes a rubric anchor to let the
  loop finish; a confirmed hard gate fails the figure regardless of the average.
- **Protect `<goals>`** — the generator makes the *same* message prettier and clearer; it never drops or
  distorts the intended message to chase a higher score.
- **One coherent revision batch per iteration**, blocks/gates first, so score moves are attributable.
- **No installs** — the skill ships no plotting deps; `<render_cmd>` runs in the user's env, helper code
  is stdlib-only; literature is the keyless S2 + arXiv core only. Never print or commit API keys
  (`keys.env` stays gitignored).

## Stops
The loop stops on the first of:
- **Pass** — `critique.pass == true`. Report the deliverable (`iter<N>/figure.png` + `plot.py`), the
  score, and the trajectory.
- **Budget** — `N == <budget>`. Report the best-scoring iteration as the deliverable.
- **Plateau** — `overall_score` flat for `<patience>` iterations. Report the best iteration + the
  standing `gate_failures`/`must_fix` blockers.

Always end with the deliverable (`iter<N>/` path), its `overall_score` and pass/fail, the per-axis
scores, the score trajectory from `ledger.tsv`, and — if it did not pass — the standing blockers
(`gate_failures` + open `must_fix`) between the figure and the bar.
