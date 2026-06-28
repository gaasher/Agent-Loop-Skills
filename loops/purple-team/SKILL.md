---
name: purple-team
description: >
  Use when the user wants to automatically harden a guardrail, classifier, content filter, prompt, or
  API they own by running attack and defense together as a closed loop, not just one or the other. It
  orchestrates the red-team and blue-team loops as independent agents: red finds distinct failure
  classes against the frozen target, blue patches the target to close them under a regression gate, then
  a fresh red pass re-verifies — confirming each class is closed and surfacing any new ones the fix
  introduced. The find→fix→re-verify cycle repeats until a fresh attack pass stays dry (the target is
  hardened) or a cycle budget is hit, then it opens a pull request with the patch set. Not for attacking
  a system the user is not authorized to test, and not for a one-shot scan — use red-team alone to only
  find, or blue-team alone to only fix.
compatibility: >
  Requires Python 3.9+ and the sibling red-team + blue-team skills installed. Real isolated subagents on
  Claude Code; runs the phases inline (serial) elsewhere. git + gh CLI for the PR handoff (degrades).
metadata:
  version: "0.1.0"
---

# Purple Team

The **combined red+blue** loop — the outer orchestration the `red-team` skill says "lives outside it."
The artifact is a target system (frozen *within* a phase, patched *between* phases); the feedback signal
is **how many new failure classes a fresh attack pass finds against the patched target**. Each cycle
runs three strictly separated phases — **find** (red-team), **fix** (blue-team), **re-verify** (a fresh
red-team pass) — and you repeat until a fresh find stays **dry** (zero new classes), meaning the target
is hardened. Red and blue run as **independent agents** so the attacker that wrote a catalogue never
grades its own patch. On stop it opens a pull request with the cycle history and the patch set.

## When to use
Use to harden a guardrail/classifier/filter/prompt/API the user owns or is authorized to test, when the
goal is an actually-hardened target plus a reviewable patch — not just a catalogue (that is `red-team`
alone) and not just closing a pre-existing catalogue (that is `blue-team` alone). It needs a runnable
oracle for the objective signal, and the two sibling skills installed.

Default: spawn red and blue as separate subagents per phase. Escape hatch: on hosts without subagent
dispatch, run each phase inline (serial) per the role files — still correct, but the same context plays
both sides, so be deliberate about not letting the fix bias the re-verify. Not for unauthorized targets.

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it, confirm the values in one line, and
skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a likely
value per binding and recommend it; on other hosts ask each as a quoted prompt. Then write
`loop.run.yaml` (format: `examples/run.example.yaml`) and confirm before creating any other files.

The phases reuse the sibling skills, so the bindings are their union — one shared `loop.run.yaml` drives
both. The same file is `<target_files>` to blue (writable) and the program behind `<target_cmd>` to red
(read-only); the same path is red's `<failures_log>` and blue's `<catalogue>`.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<target_cmd>` | run the target on one stdin input → a verdict (what red attacks) | — | the guardrail/classifier/API entrypoint |
| `<target_files>` | the source file(s) blue may edit to fix the target | — | the file(s) behind `<target_cmd>` |
| `<oracle_cmd>` | ground-truth verdict for the same input (frozen) | — | a reference checker / policy impl |
| `<gate_cmd>` | functional tests that must stay green through a fix (exits 0) | — | the target's test command; else rely on `<holdout>` |
| `<holdout>` | benign + clearly-correct inputs blue must not break | `<sandbox_root>/holdout.jsonl` | known-good inputs the oracle agrees on |
| `<catalogue>` | shared failures file: red writes it, blue closes it, JSONL `{id,text,class,...}` | `<sandbox_root>/failures.jsonl` | — |
| `<iter_strategy>` | `branches` (commit per fix → PR) or `snapshots` | `branches` | dirty/non-git tree → snapshots |
| `<pr_branch>` | branch the fixes land on and the PR opens from | `purple-team/<tag>` | today's date as `<tag>` |
| `<sandbox_root>` | where catalogues, snapshots, ledgers live | `./sandbox` | — |
| `<cycle_budget>` | max find→fix→re-verify cycles | 4 | — |
| `<find_budget>`, `<fix_budget>` | inner per-phase budgets passed to red / blue | 8 | — |

`<skill_dir>` is this skill's installed folder. The phases run the sibling skills' tools
(`red-team/tools/harness.py`, `blue-team/tools/verify.py`); the role files name them.

## The loop
Copy this checklist and tick items off each cycle. Cycles are numbered from 0; per-cycle artifacts go in
`<sandbox_root>` with the cycle index in the name so nothing is overwritten: the find catalogue is
`failures.cycle<N>.jsonl` (cycle 0 may use `<catalogue>` directly) and the re-verify result is
`failures.cycle<N>_reverify.jsonl`. The **catalogue blue fixes in cycle N is the failures file from that
cycle's find/re-verify pass** — never append back into one shared file, so each cycle's accounting is clean.

- [ ] **Cycle 0 — Find.** Run the **red-team** phase against the **frozen** target (spawn-or-degrade,
      `roles/red-find.md`), writing `failures.cycle0.jsonl`. Read back its distinct failure classes.
- [ ] If the catalogue is empty on cycle 0, **stop** — the target is already dry; report clean, no PR.
- [ ] **Fix.** Run the **blue-team** phase on this cycle's failures file (spawn-or-degrade,
      `roles/blue-fix.md`): it patches `<target_files>` one class per iteration under the gate +
      regression guard, committing kept fixes on `<pr_branch>`. Read back the classes it **closed** and
      any **residuals**.
- [ ] **Re-verify.** Run a **fresh** red-team phase against the **patched** target into
      `failures.cycle<N>_reverify.jsonl`. This confirms the closed classes no longer reproduce and
      surfaces any **new** classes the fix introduced (e.g. an over-block).
- [ ] Append one cycle row to the ledger. If the re-verify pass found new classes, they become the
      **next** cycle's catalogue (`failures.cycle<N+1>.jsonl`) — loop to **Find/Fix** for cycle N+1.
      Repeat **find→fix→re-verify** until a re-verify pass stays **dry** (no new classes) or
      `<cycle_budget>` is hit.
- [ ] **Handoff.** Open the pull request with the full cycle history (see
      [Handoff](#handoff-the-pull-request)).

**Phase independence (why three separated phases).** The target is read-only ground truth for the
duration of a red pass, so patches happen only *between* passes — mutating it mid-pass would break
reproducibility and the class accounting. Spawn red and blue as **separate** subagents so neither grades
its own work; the orchestrator only passes artifacts (the catalogue, the closed/residual summary)
between them. Launch a phase's subagent and wait for its structured return before the next phase.

## Ledger
`<sandbox_root>/cycle_ledger.tsv`, tab-separated, never commas in free text. Header
`cycle	found	fixed	residual	regressions_introduced	net_open`:
```
cycle	found	fixed	residual	regressions_introduced	net_open
0	5	5	0	1	1
1	1	1	0	0	0
```
All counts are **distinct classes**, not inner iterations: `found` = classes red surfaced this cycle;
`fixed` = classes blue *closed* (a class blue attempted several times still counts once); `residual` =
classes blue could not close; `regressions_introduced` = new classes the re-verify pass found that the
fix caused; `net_open` = classes still open entering the next cycle (`residual + regressions_introduced`,
the next cycle's catalogue size). Convergence is a re-verify pass with `net_open` = 0. Report the cycle
at which the target went dry (or the best `net_open` reached).

## Constraints
- **Authorized targets only.** This drives real attacks against the target; only run it on a system the
  user owns or is explicitly authorized to test (inherited from red-team).
- **Keep the phases independent and the ground truth frozen.** Never let one phase edit the oracle,
  `<gate_cmd>` tests, `<holdout>`, or either tool; never patch the target inside a red pass. These keep
  the find/fix/re-verify accounting honest.
- **Re-verify is a *fresh* attack, not a replay.** It must be free to find new classes (including ones
  the fix introduced), not just re-check the old list — concretely, at least half its candidates should
  be new payloads and it should try at least two attack angles not in the prior catalogue (this matters
  most in degrade mode, where the same context plays both sides). That is what makes the loop converge to dry
  rather than to "the original five are gone."
- **One change per inner iteration** (handled by the sub-loops); the orchestrator changes nothing
  itself except moving artifacts between phases.
- Stay inside the repo and `<sandbox_root>`; do not pause between phases to ask whether to continue —
  run until dry or `<cycle_budget>`.

## Handoff: the pull request
The deliverable is one **pull request** for the whole hardening run — the communication interface to the
target's owner, who keeps final approval. With the tree at blue's best state and the kept fixes already
committed on `<pr_branch>`:
- Open it with `gh pr create`; body = the cycle ledger (found → fixed → re-verified per cycle), one
  reproducible example per closed class, and any residuals still open. **Confirm once before opening** —
  it is outward-facing; never auto-push silently.
- **Degrade, don't fail:** with no remote / no `gh`, leave commits on `<pr_branch>` and write
  `git format-patch` + `PR_BODY.md` into `<sandbox_root>`; in `snapshots` mode emit a unified diff +
  `PR_BODY.md`. Tell the user the one command to open the PR themselves.

## Roles
- `roles/red-find.md` — runs the red-team phase against the target and returns the catalogue + classes.
- `roles/blue-fix.md` — runs the blue-team phase on the catalogue and returns closed classes + residuals.

Both are **spawn-or-degrade**: spawn a real isolated subagent on Claude Code (the `Agent`/Task tool),
else adopt the role inline. Each delegates to the sibling skill (`red-team` / `blue-team`) bound to the
shared `loop.run.yaml`; if a sibling is not installed, ask the user to install it (`npx skills add
gaasher/agent-loop-skills`) rather than re-implementing it here.
