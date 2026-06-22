# Authoring a loop

A loop is a self-contained folder under `loops/`. The goals, in order:
**ease of use, reach, plug-and-play.** The full rubric is
[`skill-authoring-rules.md`](skill-authoring-rules.md) — read it first; this is the quick start.

## Hard constraints

- **Self-contained folders only.** Installs copy the folder in isolation, so no `../` references and
  **no links to `docs/`** (it isn't installed) — anything needed at runtime lives inside the folder
  or in a sibling skill the loop degrades without.
- **One top-level file (`SKILL.md`).** Everything else goes in `tools/ roles/ schemas/ rubrics/
  examples/` (those five, nothing else). No per-skill README — provenance goes in the root README.
- **`name` == folder name**, lowercase-hyphen. **Programs and roles stay generic** — no hardcoded
  metrics, paths, budgets, or ledger locations; only named bindings (`<artifact>`, `<budget>`, …).
- **Spawn-or-degrade for all subagents** so loops run everywhere but get real isolation where supported.
- **Every loop keeps an append-only run ledger** so progress is reviewable.

## The five ingredients

Every loop decomposes into: a **program**, an **artifact slot**, a **feedback signal**, a
**run ledger**, and a **termination/budget**.

## SKILL.md skeleton

```markdown
---
name: <loop-name>                 # == folder name; lowercase-hyphen
description: >
  Use when the user wants to ... . <one line of what it does>. Not for ... .
compatibility: Requires Python 3.9+   # optional; only a real env requirement
metadata:
  version: "0.1.0"
---
# <Loop Name>

<1–2 sentence overview: what the loop is + its feedback signal.>

## When to use
<triggers mirroring the description; one default approach + an escape hatch.>

## Setup
Resolve bindings interactively (load `loop.run.yaml` if present, else infer+recommend on Claude Code
or ask as quoted prompts; write `loop.run.yaml` and confirm). Bindings:

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<artifact>` | ... | — | ... |

Format: `examples/run.example.yaml`.

## Loop (until <budget> or user interrupt)
Copy this checklist:
- [ ] ...
... the program ...
Append {change, signal, decision} to <ledger> each iteration.

## Ledger
<tab-separated format + a short example.>

## Constraints
- <the few hard rules, each with its reason.>
```

Copy this skeleton into `loops/<name>/SKILL.md` to start a new loop.
