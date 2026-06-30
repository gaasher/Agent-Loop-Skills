---
name: swe-loop
description: >
  Use when the user has a coding prompt — a feature, bug fix, or refactor — and wants it implemented
  end to end by a self-checking software loop, not a single pass. It refines the prompt into an
  executable plan (running the plan-loop internally), then executes the plan task by task: an Engineer
  subagent implements each PR-sized task editing only source, a separate QA subagent authors the tests
  that prove the task's acceptance criteria (or grades quality only when tests already cover them), runs
  the task's tests plus the full accumulated regression suite, and grades the code against a strict
  conciseness/readability/style-match rubric; the Engineer and QA loop on each task until the tests pass
  and the quality gate holds, then it commits and opens a pull request for the task — stacked PRs (one
  per task, each based on the prior) by default, or one combined PR — and moves to the next task. Author
  and critic have disjoint write scopes (Engineer owns source, QA owns tests) so neither can game the gate.
  Not for producing a
  plan without building it (that is plan-loop), and not for tuning a metric on an existing artifact under
  a fixed correctness bound (that is optimize-loop).
compatibility: Requires Python 3.9+ and a runnable test command in the target repo.
metadata:
  version: "0.1.0"
---

# SWE Loop

The **execute** stage of the `prompt → plan → execute → debug` pipeline: it turns a coding prompt into
working, tested, well-organised code. It runs the **plan-loop** to get an executable `tasks.json`, then
walks the tasks in dependency order. Each task is driven by two isolated subagents — an **Engineer** that
writes the code and a **QA** that owns the tests and the quality bar — looping until the gate holds. The
feedback signal is two-part, like the repo's other evaluator loops: an **objective gate** (the task's
tests pass, the full regression suite stays green, and `tools/quality_check.py` reports no threshold
violation) and a **qualitative gate** (QA's score against `rubrics/quality-rubric.md` — simplicity,
readability, comment hygiene, organisation, style-match). One task is kept per outer step; one change is
proposed per inner round, so every delta is attributable.

## When to use
Use to implement a prompt in a real repository when you want the work decomposed, built, and tested
rather than written in one shot — and when "done" means a downstream engineer would accept it: tests
green and the code clean. Default to executing the plan-loop's `tasks.json` task by task; the escape
hatch is a genuine plan defect, which becomes an `open_question` for the human rather than an improvised
detour. Simpler is better — a change that adds complexity to pass a test will be sent back by QA. Not for
planning alone (plan-loop) or for minimising a metric on a finished artifact (optimize-loop).

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it, confirm the values in one line, and
skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely
value per binding and recommend it; on other hosts ask each as a quoted prompt. Then write
`loop.run.yaml` (format: `examples/run.example.yaml`) and confirm before building anything.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<prompt>` | the coding task to build — a file path or inline text | — | the user's request |
| `<repo>` | the project to build in; the Engineer edits it | `.` | the repo being worked on |
| `<tasks_file>` | the plan-loop output the loop executes (validated by plan-loop's `validate_plan.py`) | `<sandbox_root>/tasks.json` | produced by plan-loop in Phase 0 |
| `<test_command>` | how the project's tests run | — | `tasks.json.environment.test_command`; else infer from the repo (pytest, npm test, …) |
| `<sandbox_root>` | where the plan, iteration artifacts, and ledger live | `./sandbox` | — |
| `<iter_strategy>` | `branches` (a git commit per kept task) or `snapshots` (folder copies) | `branches` | `branches` needs a clean repo |
| `<pr_mode>` | how kept tasks become PRs (see **Pull requests**): `stacked` (one PR per task, each stacked on the prior — **default**), `single` (one PR for the whole run), or `none` (local commits, no PR) | `stacked` | `single` for a small change or no stacked-PR tooling; `none` when offline / no remote |
| `<base_branch>` | the branch PRs ultimately target | `main` | the repo's default branch (`git symbolic-ref refs/remotes/origin/HEAD`) |
| `<task_budget>` | max Engineer⇄QA rounds per task | 6 | — |
| `<patience>` | stop a task after N rounds with no improvement | 2 | — |
| `<quality_thresholds>` | hard limits for `quality_check.py`: `max_comment_block`, `max_comment_line_len`, `max_func_loc`, `max_nesting`, `max_file_loc` | `8 / 100 / 60 / 4 / 400` | tighten/loosen to the repo's norms |

`<skill_dir>` is this skill's installed folder; substitute the real path in `loop.run.yaml`. The objective
quality gate each round is:
```
python3 <skill_dir>/tools/quality_check.py <changed_files> \
  --max-comment-block 8 --max-comment-line-len 100 --max-func-loc 60 --max-nesting 4 --max-file-loc 400
```

## The loop

### Phase 0 — Plan (once)
Copy this checklist and tick items off.
- [ ] **Get the plan.** If `<tasks_file>` exists and plan-loop's `validate_plan.py` passes, load it,
      confirm the objective + task count in one line, and skip to execution. Otherwise **run the
      `plan-loop` skill** on `<prompt>` grounded in `<repo>` to produce `<tasks_file>` (+ `plan.md`), and
      confirm the plan with the user before building.
- [ ] **Baseline.** Run `<test_command>` and record the set of currently-passing tests — this is the
      regression baseline every later task must preserve. Log the baseline ledger row.
- [ ] **PR preflight** (skip if `<pr_mode> = none`). Confirm a remote exists and `gh` is authed
      (`gh auth status`); resolve `<base_branch>`; pick a run tag from today's date and set
      `<run_branch>` = `swe/<tag>`. Never push to or open PRs against a branch you don't own; never force-push.

### Per task (outer loop — tasks in `tasks.json.order`)
For each task `T` in dependency order, never starting one before its `depends_on` are kept:
- [ ] **Checkpoint.** Ensure a clean tree at a known commit (the revert point for `T`). Branch model by
      `<pr_mode>`: **stacked** → cut `T`'s branch `<run_branch>/<T>` off the **previous kept task's branch**
      (or `<base_branch>` for the first task), so each task stacks on its predecessor (valid because
      `order` is topological — every `depends_on` is already in the ancestor chain). **single**/**none** →
      stay on the one work branch `<run_branch>` (cut off `<base_branch>` at the first task). In
      `snapshots` mode also copy `<repo>` into `<sandbox_root>/iter/<T>/before/`.

#### Inner loop (Engineer ⇄ QA — until `pass` or `<task_budget>`/`<patience>`)
- [ ] **Engineer** (spawn-or-degrade, `roles/engineer.md`). Give it `T`, the repo, and — on refine rounds
      — the previous `verdict.json`. It reads the neighbouring code, implements `T` editing **source
      only**, and returns `change.json` (`schemas/change.schema.json`).
- [ ] **QA** (spawn-or-degrade, `roles/qa.md`). Give it `T`, the Engineer's change, the repo, and
      `rubrics/quality-rubric.md`. It authors any missing tests for `T`'s `acceptance_criteria` (or grades
      quality only if already covered, editing **tests only**), runs `<test_command>` over the **full
      suite** (T's tests + every prior task's), runs `quality_check.py`, scores the rubric, and returns
      `verdict.json` (`schemas/verdict.schema.json`).
- [ ] **Log** a ledger row for the round.
- [ ] **Keep or refine.** If `verdict.pass` → **keep**: commit `T` (branches) / promote the working copy
      (snapshots). Then **open/refresh `T`'s PR** per `<pr_mode>` (see **Pull requests**): `stacked` →
      push `<run_branch>/<T>` and open a PR with **base = the previous task's branch** (or `<base_branch>`
      for the first task); `single` → just commit (the one PR is opened at the end); `none` → nothing.
      The regression baseline now includes `T`'s tests; break to the next task. Else feed
      `verdict.fixes` to the Engineer and refine. If the verdict doesn't improve for `<patience>` rounds
      or rounds reach `<task_budget>`, **stop the task**: revert `T`, log it `blocked`, record an
      `open_question`, and halt — do not build later tasks on an unfinished one (and do not open its PR).

The loop ends when every task in `order` is kept (the prompt is implemented and tested) or a task blocks.
On end, if `<pr_mode> = single`, push `<run_branch>` and open the one PR (base `<base_branch>`) covering
all tasks. The deliverable is the built repo plus `plan.md`, `tasks.json`, the ledger, and the PR(s).

## Pull requests (per task)
`<pr_mode>` controls how kept tasks reach the remote. A PR is opened only for a **kept** task (a
`blocked` task gets none) — it is just the delivery wrapper around an already-passing task, so the
disjoint-scope gate is unchanged. Requires `gh` authed + a remote; on a dirty tree or missing remote,
fall back to `none` and tell the user. Never force-push a pushed task branch.

- **`stacked` (default) — one PR per task.** Each task branch `<run_branch>/<T>` is cut off the previous
  kept task's branch and its PR targets that predecessor, so the stack mirrors `tasks.json` order:
  ```
  <base_branch> ◄─ PR T1 (swe/<tag>/T1) ◄─ PR T2 (base = T1) ◄─ PR T3 (base = T2) ◄─ …
  ```
  On keep: `git push -u origin <run_branch>/<T>` then
  `gh pr create --base <parent_branch> --head <run_branch>/<T> --title "<T.id>: <T.title>"
  --body "<what it delivers; Depends on #<parent PR>; tests N/N; quality minK>"`.
  Review/merge bottom-up; after a base PR merges, GitHub auto-retargets the child onto `<base_branch>`
  (or rebase the stack). Each PR stays small and independently reviewable — the point of stacking.
- **`single` — one big PR.** All tasks commit to `<run_branch>`; at loop end, one
  `gh pr create --base <base_branch>` covering the whole run. Use when reviewers want a single review or
  stacked tooling isn't available.
- **`none` — local only.** Commit per task, no push/PR (the original behaviour) — offline work, or when
  the human opens PRs themselves.

Log each PR url in the ledger `change` note.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in free text. Columns
`iter	task	phase	tests	quality	pass	note`:
```
iter	task	phase	tests	quality	pass	note
0	-	baseline	34/34	-	-	clean baseline; 34 passing tests
1	T1	engineer	-	-	-	implement config loader src/config.py
1	T1	qa	36/36	min4	yes	authored 2 tests; rubric all >=4
2	T2	engineer	-	-	-	add retry to client.py
2	T2	qa	37/38	min3	no	test_retry fails; backoff off-by-one
3	T2	qa	38/38	min2	no	tests green but readability=2: nested 5 deep
4	T2	qa	38/38	min4	yes	flattened; kept
```
`tests` is `passed/total` over the full suite; `quality` is the minimum axis score (`min4` = lowest axis
is 4); `phase` ∈ {`baseline`, `engineer`, `qa`, `keep`, `blocked`}. Report the final state at the task
that was kept or blocked.

## Constraints
- **Disjoint write scopes.** The Engineer edits only source files; QA edits only test files. This is the
  spine of the loop: the producer can't weaken the tests it's judged by, and the critic can't patch the
  source to make a test pass. A change that crosses scopes is a hard gate failure.
- **One task at a time, in dependency order**, and never build on a task that isn't kept — an unfinished
  dependency makes every later result untrustworthy.
- **The gate is non-negotiable.** A task is kept only when its tests pass, the full regression suite stays
  green, and the quality rubric holds. Tests green with ugly code is not done; clean code with a failing
  test is not done.
- **Tests are strengthen-only and bound to the plan.** QA's tests must prove the task's
  `acceptance_criteria`; never weaken, skip, or delete a passing test to get a change through.
- **Don't edit the plan to dodge work.** `tasks.json` is the contract; a real defect in it is an
  `open_question` for the human, not a quietly rewritten task.
- Run autonomously to completion or a genuine blocker; don't pause to ask "should I continue?".

## Roles
- `roles/engineer.md` — the code producer. Spawn-or-degrade: a real isolated subagent on Claude Code
  (the `Agent`/Task tool), else inline. Edits source, returns `schemas/change.schema.json`.
- `roles/qa.md` — the test author and quality critic. Spawn-or-degrade likewise. Edits tests, runs the
  suite and `tools/quality_check.py`, grades `rubrics/quality-rubric.md`, returns
  `schemas/verdict.schema.json`.

## Stops
This loop runs autonomously until every task is built and kept, or a task blocks after `<task_budget>`
rounds. On a block, stop and report the task, the standing `fixes`, and the `open_question` — surfacing a
real obstacle beats forcing a change that passes the letter of the tests but not their intent. If a task
keeps failing the same way, have the Engineer `pivot` to a different approach rather than refining a dead
end.
