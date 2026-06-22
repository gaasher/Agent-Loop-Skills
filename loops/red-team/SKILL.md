---
name: red-team
description: >
  Use when the user wants to adversarially stress-test a guardrail, classifier, prompt, or API they
  own or are authorized to test, to surface the distinct ways it fails. Generates adversarial inputs,
  runs them through the target and a ground-truth oracle, logs every target-vs-oracle disagreement as a
  failure de-duplicated by technique class, and loops until rounds stop surfacing new classes. Produces
  a catalogue of distinct, reproducible failures — the attacker half of a find→fix setup. Not for
  patching the target, and not for attacking systems the user does not own or have permission to test.
compatibility: Requires Python 3.9+
metadata:
  version: "0.1.0"
---

# Red Team

An adversarial loop-until-dry. The artifact is a target system; the feedback signal is the count of
**distinct failure classes** you can surface. Each round you craft adversarial inputs aimed at *new*
weaknesses and run them through the target and a ground-truth **oracle** via `tools/harness.py`, which
records every disagreement as a failure and de-dupes by the `class` (technique) you label each input
with. You loop until fresh rounds stop finding anything new. This is only the *find* half of a
find→fix setup: it catalogues failures and never patches the target (see [Pairing](#pairing)).

## When to use
Use to harden a guardrail, classifier, content filter, prompt, or API that the user owns or is
explicitly authorized to test — when the goal is a catalogue of distinct, reproducible failures, each
an objective target-vs-oracle disagreement. A failure is a **bypass** (target allows what the oracle
would block) or an **over-block** (target blocks what the oracle would allow).

Default: drive the loop with a runnable oracle so the signal is objective. Escape hatch: if the user
has no runnable oracle, the oracle is *your* judgment against a written policy — apply it consistently
and record the intended verdict per input. Not for fixing the target, and not for testing systems
outside the user's authorization.

## Setup
Resolve bindings interactively. If `loop.run.yaml` exists, load it, confirm the values in one line,
and skip to the loop. Otherwise: on Claude Code (the `AskUserQuestion` tool is available) infer a
likely value per binding and recommend it; on other hosts ask each as a quoted prompt. Then write
`loop.run.yaml` (format: `examples/run.example.yaml`) and confirm before creating any other files.

| binding | meaning | default | how to infer |
|---|---|---|---|
| `<target_cmd>` | system under test: reads one input on stdin, prints a verdict (`BLOCK`/`ALLOW`, a label, a score). Never edited. | — | the guardrail/classifier/API entrypoint the user names |
| `<oracle_cmd>` | ground-truth verdict for the same input. A failure is `target != oracle`. | — | a reference checker / policy impl; else your judgment vs a written policy |
| `<candidates_file>` | each round's candidates, JSONL `{id, text, class}`; `class` is the technique the harness de-dupes on | `<sandbox_root>/candidates.jsonl` | — |
| `<failures_log>` | append-only log of confirmed failures | `<sandbox_root>/failures.jsonl` | — |
| `<sandbox_root>` | where candidates, failures, and the ledger live | `./sandbox` | — |
| `<budget>` | max rounds | 8 | — |
| `<patience>` | stop after N consecutive rounds with no new failure class | 2 | — |

The signal comes from `tools/harness.py`. Run it each round:

```
python3 <skill_dir>/tools/harness.py --target "<target_cmd>" --oracle "<oracle_cmd>" \
  --inputs <candidates_file> --log <failures_log>
```

It runs both commands on every candidate and prints one JSON object:
`{tested, failures_this_run, new_classes, total_classes, examples}`.

## The loop
Copy this checklist and tick items off each round:

- [ ] Round 0 — probe: read the target's intended contract, run a small mixed batch through the
      harness to confirm wiring, note any failures it already reveals.
- [ ] Pick a fresh angle — a failure mode not yet surfaced (see the attack toolkit below).
- [ ] Generate a batch of candidates for that angle, each labeled with a root-cause `class`; write to
      `<candidates_file>`.
- [ ] Run `tools/harness.py`; read `new_classes` and the example failures.
- [ ] Record: note which new classes this round added (the harness already appended the failures and
      de-duped). Append one ledger row.
- [ ] Stop when `<patience>` consecutive rounds add no new class, or at `<budget>`. Else steer the next
      round at an untried angle.

**Attack toolkit** (draw from these, and invent your own):
- **Obfuscation** — case changes, spacing/punctuation, leetspeak, unicode homoglyphs, encoding.
- **Paraphrase / synonyms** — say the forbidden thing a different way; expand abbreviations.
- **Boundary & context** — embed the payload in benign text; multi-step or indirect phrasing.
- **Over-block probes** — benign inputs containing a trigger substring, to find false positives.

**Labeling classes.** A `class` is the root-cause technique — the single fixable weakness — not one
label per payload. Capitalizing `password`, `apikey`, and `ssn` are all the *same* class
(`case-bypass`), because one fix closes all of them; do not split them into `case-password`,
`case-apikey`, … That inflates the count so the loop never goes dry. Aim for a handful of root-cause
classes (e.g. `case-bypass`, `leetspeak`, `spacing`, `missing-synonym`, `overblock`), each
demonstrated by several payloads. Use a fresh `class` only for a genuinely new root cause; reuse a
class to add more evidence for one already found.

On stop, report: the catalogue of distinct failure classes with one reproducible example each, the
bypass/over-block split, and — since the goal is a more robust target — a short suggested fix per
class.

## Ledger
`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header `round angle tested
new_classes total_classes`:
```
round	angle	tested	new_classes	total_classes
0	probe mixed batch	6	case,spacing	2
1	leetspeak + unicode	8	leetspeak	3
2	synonyms + expansions	8	synonym,expansion	5
3	benign trigger substrings	6	overblock	6
4	multi-step phrasing	8	(none)	6
```
Report the catalogue at the round with the most distinct classes (the cumulative `total_classes`),
not whichever round ran last.

## Constraints
- **Never edit the target, the oracle, or `tools/harness.py`.** They define the system and the ground
  truth; changing them manufactures or hides failures.
- A failure is an **objective target-vs-oracle disagreement**, not a hunch — every recorded failure is
  reproducible from its input.
- **Label classes honestly and pursue new angles** — the signal is *distinct* failure modes, so do not
  pad counts by relabeling the same technique, and do not stop at the first bypass when others remain.
- Keep findings oriented toward **fixing** the target; this is robustness testing of an authorized
  system, and the catalogue exists to be handed to a fixer.
- Stay inside `<sandbox_root>`; no path escapes outside it.
- Do not pause to ask whether to continue; run until the target goes dry or hits `<budget>`.

## Pairing
This skill is the **attacker** — half of a find→fix loop. By itself it tells you *how* the system
fails but leaves it unfixed. The intended full loop pairs it with a separate coding agent that patches
the target, in three strictly separated phases:

1. **Find** *(this loop)* — run against the **frozen** target → a catalogue of distinct failure
   classes, each with a reproducible example and a suggested fix.
2. **Fix** *(a separate coding agent)* — apply patches to the target to close those classes,
   **between** runs, never inside one: the target is read-only ground truth for the duration of a run,
   so mutating it mid-loop would break reproducibility and the class accounting.
3. **Re-verify** *(a fresh find run)* — start a new run against the patched target. Confirm each prior
   class is closed and watch for regressions — especially new **over-blocks** an over-eager fix may
   introduce (this loop already hunts that direction).

Repeat find → fix → re-verify until a fresh run stays dry. Keep the two agents independent: the
attacker that wrote the catalogue should not also grade its own patch. This skill deliberately stops
at the end of phase 1; the fix/re-verify orchestration lives outside it.
