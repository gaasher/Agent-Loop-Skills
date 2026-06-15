# Authoring a loop

> Placeholder — to be expanded as the reference loops are implemented.

A loop is a self-contained folder under `loops/`. The goals, in order:
**ease of use, reach, plug-and-play.**

## Hard constraints

- **Self-contained folders only.** Installed skills are copied in isolation, so no `../`
  references that escape the loop folder — anything a loop needs lives inside it.
- **Programs and roles stay generic.** No hardcoded metrics, file paths, budgets, or
  ledger locations anywhere in `SKILL.md` or `roles/` — only named bindings like
  `<artifact>`, `<objective>`, `<direction>`, `<budget>`, `<ledger>`. Concrete values
  exist only in the user's runtime `loop.run.yaml`.
- **Spawn-or-degrade for all subagents** so loops run everywhere but get real isolation
  where the host supports it.
- **Agent Skills standard compliance** so it installs across hosts: every `SKILL.md` has
  `name`, `description`, and `metadata.version`.
- **Every loop keeps an append-only run ledger** (e.g. `runs/JOURNAL.md`) so progress is
  reviewable.

## The five ingredients

Every loop decomposes into: a **program**, an **artifact slot**, a **feedback signal**, a
**run ledger**, and a **termination/budget**.

## SKILL.md skeleton

```markdown
---
name: <loop-name>
description: Use when the user wants to ...
metadata:
  version: "0.1.0"
---
# <Loop Name>

## 1. Resolve bindings
If `loop.run.yaml` exists, load and validate it. Otherwise ask the user for the
loop's bindings, then write `loop.run.yaml` and confirm.

## 2. Run the loop (until <budget> or user interrupt)
... the program ...
Append {change, score, decision} to <ledger> each iteration.
```
