---
name: plan-loop
description: >
  Use when the user has a coding or engineering prompt and wants it refined into a detailed, executable
  plan before any code is written — the planning stage of a prompt → plan → execute → debug pipeline. It
  decomposes the prompt from first principles (objective, end state, environment, building blocks, tools,
  packages), breaks the work into PR-sized tasks each tied to a component with its files, tests, and
  dependencies, orders them topologically, splits each into atomic subtasks, then a separate
  principal-engineer agent critiques the plan for alignment, coverage, sizing, and executability; it
  revises until the critique passes, emitting a plan.md layout and a structured tasks.json that a junior
  engineer or a smaller model can execute correctly. Not for executing, scaffolding, or debugging the
  plan (those are downstream loops), and not for research proposals or experiment plans.
compatibility: Requires Python 3.9+.
metadata:
  version: "0.1.0"
---

# Plan Loop

A **planning** loop: it turns a prompt into a plan detailed and correct enough to hand to a lower-tier
model. The artifact is the plan — `plan.md` (the layout) + `tasks.json` (PR-sized tasks, each with
files, tests, dependencies, and atomic subtasks). The feedback signal is two-part, like the repo's other
evaluator loops: an **objective gate** (`tools/validate_plan.py` — schema shape, an acyclic dependency
graph, a valid topological order, full component coverage) and a **qualitative gate** (a separate
**principal engineer** agent that critiques alignment, decomposition, testability, and whether a junior
could execute each task without guessing). You build the plan from first principles, validate it,
critique it, and revise until the critique passes. This is the *plan* stage of a larger
prompt → plan → execute → debug pipeline; it stops once the plan is ready to delegate.

## When to use
Use to convert a feature/bug/refactor prompt into an executable plan grounded in a real repository —
when the goal is a hand-off artifact a downstream executor (or a smaller model) can implement
task-by-task. The plan is only as good as its weakest task for a literal-minded implementer, so the loop
optimizes for *executability*, not prose.

Default: ground the plan in the `<repo>` you are given and let the principal-engineer critique drive the
revisions. Escape hatch: if a key decision can't be resolved from the prompt or the repo, record it as an
`open_question` for the human rather than guessing. Not for writing the code (a downstream execute loop),
and not for research/experiment proposals (use `research-proposal`).

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it, confirm the values in one line, and
skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely
value per binding and recommend it; on other hosts ask each as a quoted prompt. Then write
`loop.run.yaml` (format: `examples/run.example.yaml`) and confirm before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<prompt>` | the task to plan — a file path or inline text | — | the user's request |
| `<repo>` | the project the plan targets; read for ground-truth env + conventions (never edited) | `.` | the repo being worked on |
| `<plan_file>` | the human-readable plan layout (markdown) | `<sandbox_root>/plan.md` | — |
| `<tasks_file>` | the structured tasks, validated against `schemas/plan.schema.json` | `<sandbox_root>/tasks.json` | — |
| `<pr_loc>` | target lines of code per task (PR-sized; a task may exceed it) | `100-400` | — |
| `<sandbox_root>` | where plan, tasks, and the ledger live | `./sandbox` | — |
| `<budget>` | max refine cycles | 5 | — |

`<skill_dir>` is this skill's installed folder; substitute the real path when writing `loop.run.yaml`.
The objective gate runs each cycle:
```
python3 <skill_dir>/tools/validate_plan.py --tasks <tasks_file>
```
It prints one JSON object `{ok, errors, warnings, stats}` — `ok` must be true (no errors) before a plan
is considered ready.

## The loop
Copy this checklist and tick items off.

**Build the plan (iteration 0 — first principles):**
- [ ] **Ground.** Read `<prompt>` and inspect `<repo>` for ground truth: language, package manager,
      runtime/OS, the test command, and existing modules/conventions to reuse. Check what you can; never
      assume what you can read.
- [ ] **Decompose.** Lay out the components from first principles — **objective**; **end state /
      definition of done**; **non-goals**; **environment**; **building blocks**; **interfaces/contracts**
      between blocks; **tools**; **packages**; **data/assets**; **reuse** (existing code + installed
      skills); **open questions**. Recursively split any component too big to reason about in one piece.
- [ ] **Tasks (PR-sized).** Break the work into tasks, each ~`<pr_loc>` and equivalent to one PR. For
      each record: which components it `serves`, a description, building_blocks/tools/packages, the exact
      `files` it creates/modifies, `tests` that prove it, `acceptance_criteria`, and `estimated_loc`.
- [ ] **Order.** Fill each task's `depends_on`, then compute a topological `order` (every task after its
      dependencies).
- [ ] **Subtasks.** Split each task into atomic subtasks a junior can do with no further decisions —
      "create file X", "define function `f(args) -> T`", "wire f into Y".
- [ ] **Write + validate.** Write `<plan_file>` and `<tasks_file>`, then run `tools/validate_plan.py`;
      fix every error and weigh every warning before the first critique. Log the baseline ledger row.

**Refine (repeat until the plan passes or `<budget>`):**
- [ ] **Critique.** Spawn the principal engineer (spawn-or-degrade, `roles/principal-engineer.md`) with
      the prompt, the repo, `plan.md`, `tasks.json`, the latest `validate_plan.py` output, and the **list
      of installed skills** on this host. It returns a structured critique
      (`schemas/critique.schema.json`): verdict, score, issues (blocking/major/minor, each with a fix),
      coverage gaps, and suggested skills.
- [ ] **Revise.** Apply the fix for **every blocking and major issue** — re-decompose, re-size, re-order,
      add tests, pin packages, add concrete signatures/paths/data shapes so a junior can't go wrong.
      Re-run `tools/validate_plan.py`. Append a ledger row.
- [ ] **Stop** when the critique returns `pass` (no blocking or major issues) **and** the validator is
      clean — the plan is ready to delegate. Else loop, up to `<budget>`; if the score plateaus with only
      minor issues, stop and record them as open notes.

On stop, the deliverable is `<plan_file>` + `<tasks_file>` (plus any `open_questions` for the human),
built to be executed task-by-task in `order` by a downstream execute loop or a lower-tier model.

## Plan artifacts
**`<tasks_file>` (tasks.json)** — the machine-executable plan; full contract in `schemas/plan.schema.json`.
Compact shape:
```json
{
  "objective": "...", "end_state": "...", "non_goals": ["..."],
  "environment": {"language": "python", "package_manager": "uv", "test_command": "pytest -q"},
  "components": [{"id": "c1", "name": "config", "description": "load + validate config"}],
  "open_questions": ["which auth provider?"],
  "tasks": [
    {"id": "T1", "title": "config loader", "serves": ["c1"], "description": "...",
     "building_blocks": ["dataclass Config"], "tools": ["pytest"], "packages": ["pyyaml"],
     "files": [{"path": "src/config.py", "action": "create", "what": "Config + load()"}],
     "subtasks": [{"id": "T1.1", "description": "define load(path) -> Config"}],
     "tests": [{"description": "load() parses a valid file", "kind": "unit"}],
     "acceptance_criteria": ["invalid config raises ConfigError"],
     "depends_on": [], "estimated_loc": 180, "suggested_skills": []}
  ],
  "order": ["T1"]
}
```
**`<plan_file>` (plan.md)** — the human-readable layout: objective, end state, non-goals, environment,
the components, a task table (id · title · serves · depends_on · est. LOC) in `order`, risks/open
questions, and a one-line "how to execute" pointer to tasks.json. It mirrors tasks.json; tasks.json is
the source of truth the executor consumes.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text. Header
`iter	phase	verdict	score	blocking	major	change`:
```
iter	phase	verdict	score	blocking	major	change
0	build	-	-	-	-	first-principles decomposition: 6 components, 8 tasks, validator ok
1	critique	revise	72	1	2	PE: T3 bundles 2 PRs; T5 has no real test; nothing covers config loading
2	revise	-	-	-	-	split T3 -> T3a/T3b; added retry test to T5; added T9 config loader; reordered
3	critique	pass	90	0	0	PE: solid; one minor naming nit recorded as an open note
```
Report the final plan at the cycle the critique passed (or the best score reached at `<budget>`).

## Constraints
- **Plan only — do not implement.** Write no production code, scaffolding, or files in `<repo>`; the
  output is `plan.md` + `tasks.json`. Execution and debugging are downstream loops.
- **Ground every claim in the real repo/environment.** Do not invent packages, files, APIs, or commands;
  verify against `<repo>`. A genuine unknown is an `open_question` for the human, not a guess — a plan
  that confidently states something false is worse than one that flags the gap.
- **Keep tasks PR-sized and self-contained.** Each task links to ≥1 component and has tests and
  acceptance criteria; each subtask is atomic. Optimize for a literal implementer who will not fill gaps.
- **Keep the critic independent.** The principal engineer reviews the plan it did not write
  (spawn-or-degrade gives real isolation on Claude Code); never let the author pass its own plan.
- **Edit only inside `<sandbox_root>`** (plan, tasks, ledger); `<repo>` is read-only context. Run the
  loop to a passing critique or `<budget>` without pausing to ask whether to continue.

## Roles
`roles/principal-engineer.md` — the adversarial plan critic. Spawn-or-degrade: a real isolated subagent
on Claude Code (the `Agent`/Task tool), else adopt the role inline. It is read-only, judges against a
fixed rubric, and returns JSON validated against `schemas/critique.schema.json`. Pass it the host's
installed-skill list so it can recommend reuse; if that list is unavailable, it simply skips
`suggested_skills`.
