# Skill authoring rules

The rubric every loop in this repo is written against. Distilled from
[Anthropic's skill best-practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
[Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills),
the K-Dense scientific-skill libraries, and 2026 loop-engineering practice. Read this before
writing or editing any `SKILL.md`; re-check against the [checklist](#checklist) before it ships.

## Contents
- [The five ingredients](#the-five-ingredients)
- [File layout](#file-layout)
- [Frontmatter](#frontmatter)
- [Body: concise + progressive disclosure](#body-concise--progressive-disclosure)
- [Instruction style](#instruction-style)
- [Degrees of freedom](#degrees-of-freedom)
- [Tools (scripts)](#tools-scripts)
- [Roles and spawn-or-degrade](#roles-and-spawn-or-degrade)
- [Bindings and the ledger](#bindings-and-the-ledger)
- [Package / dependency policy](#package--dependency-policy)
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
A skill is a **self-contained** folder under `loops/<name>/` (no `../` escapes — installs copy the
folder in isolation). Exactly **one top-level file: `SKILL.md`**. Everything else goes in a folder:
- `tools/` — vendored helper scripts (stdlib-only; see [Tools](#tools-scripts)).
- `roles/` — sub-agent role prompts for multi-role loops.
- `schemas/` — JSON schemas for structured outputs.

No `README.md` inside a skill folder. No bundled fixtures — **test cases live in `sandbox/`**.
All paths use forward slashes. Helpers are 3.9-safe (no `match`, no `X | Y` unions).

## Frontmatter
Two required fields; the `description` is the single most important line in the file because it is
what the host uses to decide whether to load the skill.
- `name`: lowercase letters, numbers, hyphens; ≤64 chars; no `claude`/`anthropic`. (This repo uses
  existing camelCase folder names like `codeRefactorLoop` for the folder, but the `name:` field
  stays lowercase-hyphen, e.g. `code-refactor-loop`.)
- `description`: **third person**, ≤1024 chars, states **what it does + when to use it**, with
  specific trigger terms. Be slightly "pushy" — skills tend to under-trigger.

```yaml
---
name: code-refactor-loop
description: >
  Use when the user wants to iteratively refactor a code module — improving readability and
  reducing complexity while a test suite stays green. Each iteration edits the module, runs the
  tests (hard gate) and a complexity metric, and keeps the change only if tests pass and
  complexity drops; loops until a plateau or the iteration budget.
metadata:
  version: "0.1.0"
---
```

## Body: concise + progressive disclosure
- **Assume Claude is smart.** Only add context it does not already have. Challenge every paragraph:
  does it justify its token cost? Cut explanations of well-known concepts.
- **Keep `SKILL.md` under ~500 lines.** When it grows past that, move detail into `tools/`/`roles/`/
  `schemas/` and reference it.
- **`SKILL.md` is a table of contents**, not an encyclopedia. References stay **one level deep**
  (link directly from `SKILL.md`, not file→file→file). Put a short ToC atop any file >100 lines.
- **Consistent terminology** — one term per concept throughout. **No time-sensitive info**
  ("as of June 2026…"); put deprecated guidance in an "old patterns" aside if ever needed.

## Instruction style
- **State the rule, then why.** Reasoning lets the model generalize to cases you did not anticipate.
  Prefer "Edit only files in `<editable_files>`, because every other file is the evaluation ground
  truth" over a bare "NEVER edit other files."
- Reserve emphatic, low-freedom language for the few steps where consistency is critical (e.g. "run
  exactly this command"). Over-using all-caps MUST/NEVER flattens the signal.
- Use **checklists** for multi-step workflows so progress is trackable and steps are not skipped.

## Degrees of freedom
Match specificity to how fragile/variable the step is:
- **High** (prose steps) — many valid approaches, context decides. e.g. "pick one experimental idea".
- **Medium** (parameterized scripts/pseudocode) — a preferred pattern with some variation.
- **Low** (exact scripts, no options) — fragile or consistency-critical. e.g. "run `tools/bench.py`".

## Tools (scripts)
Prefer a **script over prose** for any deterministic operation (measuring, validating, hashing):
scripts are more reliable, save tokens, and stay consistent across runs.
- **Stdlib-only**, no installs, 3.9-safe. The whole repo is `dependencies = []` by design.
- **Solve, don't punt** — handle the error conditions in the script rather than failing to Claude.
- **No voodoo constants** — justify/comment every magic number (timeouts, iteration caps).
- Make execution intent explicit: "**Run** `tools/metrics.py <file>`" (execute) vs "**See**
  `tools/metrics.py` for the algorithm" (read). Execution is the default.
- Verbose, actionable error messages (name the offending field/value and the available options).

## Roles and spawn-or-degrade
Multi-role loops (judge / critic / mutator / reviser) keep each role prompt in `roles/`.
**Spawn-or-degrade**: spawn a real isolated subagent where the host supports it (Claude Code:
`Agent`), and otherwise adopt the role inline in the same context. Detect the host once (is
`AskUserQuestion` available?) and branch on it.

## Bindings and the ledger
- **No hardcoded paths/metrics/budgets** anywhere in `SKILL.md` or `roles/` — only named bindings
  (`<artifact>`, `<objective>`, `<budget>`, `<ledger>`, …). Concrete values live only in the user's
  runtime `loop.run.yaml`/`schema.yaml`.
- **Resolve bindings interactively** at setup: on Claude Code, infer a likely value and present it as
  the recommended option via `AskUserQuestion`; otherwise ask as a quoted plain-text prompt. Write a
  `loop.run.yaml`/`schema.yaml` so the run is reproducible and **non-interactive re-runs skip setup**.
- **Append to the ledger every iteration**: tab-separated, never commas in free text. Report the
  **best** iteration (not necessarily the last) when stopping on budget/plateau.

## Package / dependency policy
Two cases, handled differently (K-Dense-informed):
- **Our `tools/` helpers and all sandbox test cases: stdlib-only, zero install, always.** They must
  run on a bare `python3` (3.9+).
- **Where a loop runs the *user's* artifact** (their analysis/training/query code): use the user's
  bound run command/environment. Probe optional accelerators with `try/except ImportError` and
  **degrade to the stdlib path** when absent. If a package genuinely helps and is missing, surface a
  consented, **version-pinned `uv pip install "<pkg>==<ver>"`** (the K-Dense house style) — never a
  silent install, never a hard stop. Declare optional deps + the Python floor in the binding setup.

## Testing: eval-driven, Sonnet-run
- **Build the test case first.** A loop's evaluation is its source of truth; write it before polishing
  prose. Each loop gets a `sandbox/` case: a small artifact + a `loop.run.yaml` of pre-resolved
  bindings + the ground-truth signal (a tiny `unittest` suite / seeded SQLite / labeled eval set /
  planted bug). Size it to run end-to-end in ≤~10 min with a low iteration budget (3–5).
- **Run with the models you ship for.** Here we exercise each loop by spawning a Sonnet subagent
  against its sandbox case, then **iterate from observed behavior** — where it struggled, what it
  skipped — improving the skill (tooling, prompts, roles), not just guessing.
- A good run shows the ledger signal moving the right way (complexity ↓ with tests green; failures
  climbing then saturating) and the final artifact passing the ground-truth check.

## Anti-patterns
- Vague description ("helps with data") → the skill never triggers.
- Over-describing the whole workflow in the description → the host skips loading the body.
- Dumping everything into one giant `SKILL.md` → blows the context budget; use progressive disclosure.
- Offering many options ("use pdfplumber or PyMuPDF or…") → give one default + an escape hatch.
- Assuming packages are installed; Windows-style backslash paths; hardcoded metrics/paths/budgets.
- Bare all-caps directives with no reason → the model can't generalize to edge cases.
- Nested references (file→file→file) → Claude partial-reads and misses content.

## Checklist
Before a skill ships:
- [ ] `description` is third-person, specific, includes triggers, says what + when.
- [ ] `name` is lowercase-hyphen, ≤64, no reserved words; `metadata.version` present.
- [ ] Body <500 lines; concise; consistent terms; no time-sensitive info.
- [ ] Exactly one top-level file (`SKILL.md`); extras in `tools/`/`roles/`/`schemas/`; no README.
- [ ] References one level deep; ToC on any file >100 lines.
- [ ] All five ingredients present; signal is objective + locally runnable where possible.
- [ ] Bindings (no hardcoded values); interactive setup writes `loop.run.yaml`; append-only ledger.
- [ ] `tools/*` are stdlib-only, 3.9-safe, solve-don't-punt, no voodoo constants, forward-slash paths.
- [ ] Spawn-or-degrade for any sub-role.
- [ ] A `sandbox/` test case exists and was run with Sonnet; the skill was iterated from the result.
