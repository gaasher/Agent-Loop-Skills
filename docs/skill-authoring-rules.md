# Skill authoring rules

The rubric every loop in this repo is written against. Distilled from
[Anthropic's skill best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills),
the [Agent Skills open spec](https://agentskills.io/specification), and the
[K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) library.
Read this before writing or editing any `SKILL.md`; re-check against the [checklist](#checklist)
before it ships.

## Contents
- [The five ingredients](#the-five-ingredients)
- [File layout](#file-layout)
- [Frontmatter](#frontmatter)
- [Body: order + progressive disclosure](#body-order--progressive-disclosure)
- [Setup: the bindings protocol](#setup-the-bindings-protocol)
- [Schemas and examples](#schemas-and-examples)
- [Instruction style](#instruction-style)
- [Degrees of freedom](#degrees-of-freedom)
- [Tools (scripts)](#tools-scripts)
- [Roles and spawn-or-degrade](#roles-and-spawn-or-degrade)
- [Bindings and the ledger](#bindings-and-the-ledger)
- [The environment contract](#the-environment-contract)
- [Testing: eval-driven, Sonnet-run](#testing-eval-driven-sonnet-run)
- [Anti-patterns](#anti-patterns)
- [Checklist](#checklist)

## The five ingredients
Every loop decomposes into the same parts. If one is missing, the loop is underspecified.
1. **Program** — the orchestration instructions in `SKILL.md`.
2. **Artifact slot** — the thing being improved (code, a query, a prompt, a hypothesis set…), named
   as a binding (`<artifact>`), never hardcoded.
3. **Feedback signal** — the score/critique that decides the next step. Prefer an **objective,
   locally-runnable** signal (tests, latency, a coverage/complexity number, a verified-claim count).
4. **Run ledger** — an append-only `ledger.tsv` recording `{change, signal, decision}` per iteration.
5. **Termination / budget** — an explicit stop: a threshold, a plateau (no improvement for K rounds),
   loop-until-dry (no new findings for K rounds), or an iteration budget.

## File layout
A skill is a **self-contained** folder under `loops/<name>/`. Installs copy the folder in isolation
(`cp -r loops/* ~/.claude/skills/`), so **nothing outside the folder is available at runtime** — no
`../` escapes, and **no links to `docs/`** (which is not installed). Anything an installed skill needs
at runtime lives inside its folder or in a sibling skill it degrades without.

Exactly **one top-level file: `SKILL.md`**. Everything else goes in one of exactly **five** folders:
- `tools/` — executable helper scripts and code packages (stdlib-only; see [Tools](#tools-scripts)).
- `roles/` — sub-agent role prompts for multi-role loops.
- `schemas/` — JSON schemas for **structured subagent/tool output** (see [Schemas](#schemas-and-examples)).
- `rubrics/` — grading rubrics referenced by judge/evaluator roles.
- `examples/` — worked examples: the `run.example.yaml` bindings config, and sample artifacts.

No `README.md` inside a skill folder (provenance/credits go in the **root** README). No bundled
fixtures — **test cases live in `sandbox/`** (gitignored). All paths use forward slashes.

## Frontmatter
Two required fields; `description` is the single most important line in the file because it is what
the host uses to decide whether to load the skill.
- `name`: **must equal the folder name**; lowercase letters, numbers, hyphens; ≤64 chars; no leading/
  trailing/consecutive hyphens; no `claude`/`anthropic`; no XML tags. (Folder == `name` is a spec
  requirement — strict validators reject a mismatch.)
- `description`: **third person**, ≤1024 chars. **Lead with `Use when…`** triggers (specific terms —
  skills under-trigger, so be pushy), then a brief *what it does*. Add **negative triggers**
  (“Not for …”) where confusable. **Do not encode the full workflow or step counts** — an agent may
  follow the description instead of reading the body.
- `metadata.version`: a quoted version string (no top-level `version` field exists in the spec).
- `compatibility` *(optional)*: real env requirements only, ≤500 chars, e.g. `Requires Python 3.9+`.

```yaml
---
name: code-refactor-loop          # == folder name; lowercase-hyphen; no claude/anthropic
description: >
  Use when the user wants to iteratively refactor a code module — cut complexity while a test suite
  stays green. Applies one focused refactor per iteration, runs the tests (hard gate) and a
  complexity metric, keeps the change only if tests pass and complexity drops, else reverts; loops to
  a plateau or budget. Not for adding features or fixing bugs.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---
```

## Body: order + progressive disclosure
Use this section order (matches the spec + Anthropic's `skill-creator`):
1. `# Title` — human-readable name.
2. **Overview** — 1–2 sentences: what this loop is and its feedback signal. Assume Claude is smart;
   only add what it doesn't already know.
3. `## When to use` — mirror the description's triggers; one default approach + an escape hatch.
4. `## Setup` — resolve bindings (see [the protocol](#setup-the-bindings-protocol)).
5. `## Loop` — the program. Open with a copy-able `- [ ]` checklist of the iteration steps.
6. `## Ledger` — the append-only `ledger.tsv` format + a short example.
7. `## Constraints` — the few hard rules, each with its reason.
8. *(optional)* `## Stops` — explicit termination conditions if not obvious from the loop.

Rules:
- **Keep `SKILL.md` under ~500 lines** (< ~5000 tokens). Past that, move detail into
  `tools/`/`roles/`/`schemas/`/`rubrics/` and reference it.
- **References stay one level deep** — link directly from `SKILL.md`, never file→file→file (Claude
  partial-reads nested refs and misses content). Put a short ToC atop any file >100 lines.
- **Consistent terminology** — one term per concept. **No time-sensitive info**.

## Setup: the bindings protocol
Every loop resolves its bindings the same way. State it **tersely** (don't re-derive the protocol per
loop) and put the per-loop specifics in a **bindings table**. The whole `## Setup` should be ~15–25
lines:

> **Resolve bindings interactively.** If `loop.run.yaml` exists in the working dir, load it and skip
> to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely
> value for each binding and present it as the recommended option; on other hosts ask each as a
> quoted plain-text prompt. Then write `loop.run.yaml` (format: `examples/run.example.yaml`) and
> confirm the values before creating any other files.

Then a table — the only per-loop setup content:

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<artifact>` | the file(s) to improve | — | scan for the primary source file |
| `<run_cmd>` | command that runs the artifact in the user's env | — | `pyproject.toml`/`.venv`/README |
| `<budget>` | max iterations | 8 | — |

Loops that use literature search add **one line**, not a section: “Paper search goes through the
sibling `literature-search` skill (`<lit> = python3 <lit_skill_dir>/tools/lit_search.py`); if it is
absent, degrade to WebSearch/WebFetch.”

## Schemas and examples
Two different artifacts are often both called “schema” — keep them straight:
- **Config / bindings** (the `loop.run.yaml`) is **not** a schema. Ship **one concrete**
  `examples/run.example.yaml`; the body already documents the bindings in its table. Do **not** ship a
  separate per-loop config-schema file — that is bloat (K-Dense ships none).
- **Structured output** — a `schemas/*.json` (JSON Schema draft-07) is worth keeping **only when a
  subagent or tool must emit machine-validated data** (e.g. a Judge `verdict.json`, a proposer
  `idea.json`). The value is the enforce→fix→repeat loop. If nothing validates against it, delete it.

Whenever a schema or rubric is referenced, show a **compact generic example instance** inline next to
the reference (e.g. an abridged `verdict.json`) so the reader sees the shape without opening the file.

## Instruction style
- **State the rule, then why.** Reasoning lets the model generalize to cases you didn't anticipate.
  Prefer “Edit only files in `<editable_files>`, because every other file is the evaluation ground
  truth” over a bare “NEVER edit other files.”
- The **description is third person**; the **body is imperative** (“Run X”, “Edit only Y”).
- Reserve emphatic MUST/NEVER for the few consistency-critical steps; overuse flattens the signal.
- Use a copy-able **`- [ ]` checklist** for the loop so steps are trackable and not skipped.

## Degrees of freedom
Match specificity to how fragile/variable the step is:
- **High** (prose steps) — many valid approaches, context decides. e.g. “pick one experimental idea”.
- **Medium** (parameterized scripts/pseudocode) — a preferred pattern with some variation.
- **Low** (exact scripts, no options) — fragile or consistency-critical. e.g. “run `tools/bench.py`”.

## Tools (scripts)
Prefer a **script over prose** for any deterministic operation (measuring, validating, hashing):
scripts are more reliable, save tokens, and stay consistent across runs.
- **Stdlib-only**, no installs, 3.9-safe (no `match`, no `X | Y` unions). The whole repo is
  `dependencies = []` by design, so helpers run on a bare `python3` — even on the no-network API.
- **Defer heavy imports inside functions** (`try: import pandas` inside the function, not at module
  top) so the script still loads when the lib is absent — then degrade or emit an install hint.
- **Solve, don't punt** — handle error conditions in the script rather than failing to Claude.
- **No voodoo constants** — justify/comment every magic number (timeouts, iteration caps).
- Make execution intent explicit: “**Run** `tools/metrics.py <file>`” (execute) vs “**See**
  `tools/metrics.py` for the algorithm” (read). Execution is the default.
- Verbose, actionable error messages (name the offending field/value and the available options).

## Roles and spawn-or-degrade
Multi-role loops (judge / critic / mutator / reviser) keep each role prompt in `roles/`, self-contained
and generic (named bindings, no hardcoded values). **Spawn-or-degrade**: spawn a real isolated
subagent where the host supports it, otherwise adopt the role inline in the same context. Runtime
dispatch of an arbitrary role file is **confirmed only on Claude Code** (the `Agent` / `Task` tool); on other
hosts the role runs inline — so never assume real isolation off Claude Code. Detect the host once (is
`AskUserQuestion` available?) and branch. Launch
independent subagents **in one turn** for parallelism; require a structured return (validate against
the role's `schemas/*.json`). See [`compatibility.md`](compatibility.md) for which hosts get real
isolation vs. the inline fallback.

## Bindings and the ledger
- **No hardcoded paths/metrics/budgets** anywhere in `SKILL.md` or `roles/` — only named bindings
  (`<artifact>`, `<objective>`, `<budget>`, `<ledger>`, …). Concrete values live only in the user's
  runtime `loop.run.yaml`.
- **Append to the ledger every iteration**: tab-separated, never commas in free text. Report the
  **best** iteration (not necessarily the last) when stopping on budget/plateau.

## The environment contract
Three tiers, handled differently (K-Dense-confirmed). **A skill never ships or downloads heavy deps.**
- **Tier A — the skill's own `tools/`: stdlib-only, zero-install, always.** Runs on bare `python3`
  (3.9+), so it works even on the no-network Claude API. Declare the floor in `compatibility:`.
- **Tier B — the user's artifact** (their training/analysis/query code): run it via the **bound
  `<run_cmd>`/`<analysis_cmd>` in the user's own environment** (e.g. `/path/to/venv/bin/python
  train.py` or `uv run train.py`). The skill never imports torch et al.; it shells out and reads
  outputs (`metrics.json`, stdout). Analysis code the skill writes runs under that same interpreter —
  so running the user's torch code for analysis is fair game, with zero bundling.
- **Tier C — a skill-owned script that genuinely needs a third-party package:** do not bundle it and
  do not silently install. Probe with `try/except ImportError`; degrade to the stdlib path when
  absent; if it genuinely helps, surface a **consented, version-pinned** install — prefer **PEP 723
  inline deps + `uv run`** (the dep travels with the script, resolved on demand into a cache), else a
  copy-pasteable `uv pip install "<pkg>==<ver>"` hint. Never silent, never a hard stop.

**API keys.** Skills that call external APIs share one gitignored `keys.env` at the project root (all
keys optional, presence read as booleans, never pasted into chat). The installed reference
implementation is the `literature-search` skill (`<lit> keys --init`); a new skill that needs its own
keys copies the `literature-search` skill's `tools/lit/keys.py` into its `tools/`. See
[`api-keys.md`](api-keys.md) — an authoring
reference; an installed `SKILL.md` reaches the convention through the sibling skill, never via `docs/`.

## Testing: eval-driven, Sonnet-run
- **Build the test case first.** A loop's evaluation is its source of truth. Each loop gets a
  `sandbox/` case: a small artifact + a `loop.run.yaml` of pre-resolved bindings + the ground-truth
  signal (a tiny `unittest` suite / seeded SQLite / labeled eval set / planted bug). Size it to run
  end-to-end in ≤~10 min with a low iteration budget (3–5).
- **Run with the models you ship for.** Exercise each loop by spawning a Sonnet subagent against its
  sandbox case, then **iterate from observed behavior** — where it struggled, what it skipped.
- A good run shows the ledger signal moving the right way and the final artifact passing the
  ground-truth check.

## Anti-patterns
- Vague description ("helps with data") → the skill never triggers.
- Encoding the whole workflow/step-count in the description → the host follows it instead of the body.
- Dumping everything into one giant `SKILL.md` → blows the context budget; use progressive disclosure.
- **Linking `docs/` or using `../` from an installed `SKILL.md`** → dead link after install.
- Shipping a per-loop config-schema file → bloat; a `run.example.yaml` + the bindings table suffice.
- Offering many options ("use pdfplumber or PyMuPDF or…") → give one default + an escape hatch.
- Assuming packages are installed; importing heavy libs at module top; hardcoded metrics/paths/budgets.
- Bare all-caps directives with no reason → the model can't generalize to edge cases.
- Nested references (file→file→file) → Claude partial-reads and misses content.

## Checklist
Before a skill ships:
- [ ] `name` == folder name, lowercase-hyphen, ≤64, no reserved words; `metadata.version` present.
- [ ] `description` is third-person, leads with `Use when…`, specific triggers, no step counts.
- [ ] Body order: Title → Overview → When to use → Setup → Loop (+`[ ]` checklist) → Ledger →
      Constraints. Under ~500 lines; consistent terms; no time-sensitive info.
- [ ] Exactly one top-level file (`SKILL.md`); extras only in `tools/ roles/ schemas/ rubrics/
      examples/`; no README.
- [ ] No `../` escapes and **no runtime `docs/` links**; references one level deep; ToC on files >100 ln.
- [ ] All five ingredients present; signal is objective + locally runnable where possible.
- [ ] Setup is the terse protocol + a bindings table; one `examples/run.example.yaml`.
- [ ] `schemas/*.json` only where a subagent/tool emits validated output; generic instance shown inline.
- [ ] `tools/*` stdlib-only, 3.9-safe, deferred heavy imports, solve-don't-punt, forward-slash paths.
- [ ] Environment: user artifact via bound `<run_cmd>`; no bundled deps; consented pinned installs only.
- [ ] Spawn-or-degrade for any sub-role.
- [ ] A `sandbox/` test case exists and was run with Sonnet; the skill was iterated from the result.
