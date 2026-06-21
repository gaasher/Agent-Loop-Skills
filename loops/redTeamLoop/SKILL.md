---
name: red-team-loop
description: >
  Use when the user wants to adversarially stress-test their own system — a guardrail, classifier,
  prompt, or API — to surface the distinct ways it fails. Each round generates a batch of adversarial
  inputs aimed at new failure modes, runs them against the target and a ground-truth oracle, and logs
  every disagreement as a failure, de-duplicated by technique; it loops until rounds stop surfacing new
  failure classes (goes dry) or the budget is hit. The result is a catalogue of distinct, reproducible
  failures. For authorized robustness testing of systems you own or are permitted to test.
metadata:
  version: "0.1.0"
---

# Red Team Loop

An **adversarial loop-until-dry**. The artifact is a target system; the feedback signal is the
**count of distinct failure classes** you can surface. Each round you craft adversarial inputs aimed
at *new* weaknesses, run them through the target and a ground-truth **oracle**, and record every
disagreement as a failure. You keep going until fresh attack rounds stop finding anything new.

A "failure" is an objective disagreement between the **target** (the system under test) and the
**oracle** (what the correct verdict should be): the target lets through what it should stop (a
**bypass**) or stops what it should allow (an **over-block**). The signal comes from
`tools/harness.py`, which runs both, logs disagreements, and **de-duplicates by the `class`
(technique) you label each input with** — so progress is measured in *distinct* failure modes, not
raw counts.

> Scope: this is for testing systems you own or are explicitly authorized to test, to make them more
> robust. Keep findings in service of fixing the target.

---

## 1. Resolve bindings (setup — once)

If a `loop.run.yaml` exists, load it, confirm the values in one line, and skip to §2. Otherwise
resolve each binding, then write `loop.run.yaml` so re-runs are non-interactive.

**Detect host:** if `AskUserQuestion` is available you are in **Claude Code** — infer a likely value
and present it as the recommended option. Otherwise ask each as a quoted plain-text prompt.

- **`<target_cmd>`** — the system under test, as a command that reads one input on stdin and prints a
  verdict (e.g. `BLOCK`/`ALLOW`, a label, a score). This is what you attack; never edit it.
- **`<oracle_cmd>`** — the ground-truth judgment for the same input: a command (a reference checker,
  a policy implementation) that prints the *correct* verdict. A failure is `target ≠ oracle`. If the
  user has no runnable oracle, the oracle is *your* judgment against a written policy — apply it
  consistently and record the intended verdict per input.
- **`<candidates_file>`** — where you write each round's candidate inputs (JSONL `{id, text, class}`;
  default `<sandbox_root>/candidates.jsonl`). `class` is the technique label the harness de-dupes on.
- **`<failures_log>`** — append-only log of confirmed failures (default `<sandbox_root>/failures.jsonl`).
- **`<harness_cmd>`** — default
  `python3 <skill_dir>/tools/harness.py --target "<target_cmd>" --oracle "<oracle_cmd>" --inputs <candidates_file> --log <failures_log>`.
  It prints `{tested, failures_this_run, new_classes, total_classes, examples}`.
- **`<sandbox_root>`** (default `./sandbox/`), **`<budget>`** (default 8 rounds), **`<patience>`**
  (default 2 — stop after this many consecutive rounds with no new failure class).

**Confirm and go.** Print the bindings; create nothing until the user confirms (skip only when
`loop.run.yaml` already existed). Then initialise the ledger (§3) and start.

---

## 2. The loop

**Round 0 — probe.** Read the target's intended contract (its policy, or a few example inputs/outputs)
and run a small mixed batch through `<harness_cmd>` to confirm the wiring and see what the target does
on obvious cases. Note any failures it already reveals.

**Then, until stop (dry or budget):**

1. **Pick a fresh angle.** Choose a failure mode you have **not** yet surfaced. Draw from the attack
   toolkit (and invent your own):
   - **Obfuscation** — case changes, spacing/punctuation, leetspeak, unicode homoglyphs, encoding.
   - **Paraphrase / synonyms** — say the forbidden thing a different way; expand abbreviations.
   - **Boundary & context** — embedding the payload in benign text, multi-step or indirect phrasing.
   - **Over-block probes** — benign inputs that contain a trigger substring, to find false positives.
2. **Generate a batch** of candidates for that angle, each labeled with a `class`, and write them to
   `<candidates_file>`. **A `class` is the root-cause technique — the single fixable weakness — not one
   label per payload.** Capitalizing `password`, `apikey`, and `ssn` are all the *same* class
   (`case-bypass`), because one fix closes all of them; do **not** split them into `case-password`,
   `case-apikey`, … That inflates the count and means the loop never goes dry. Aim for a handful of
   root-cause classes (e.g. `case-bypass`, `leetspeak`, `spacing`, `missing-synonym`, `overblock`),
   each demonstrated by several payloads. Use a fresh `class` only for a genuinely new root cause;
   reuse a class to add more evidence for one already found.
3. **Run** `<harness_cmd>`. Read `new_classes` and the example failures.
4. **Record.** The harness appended confirmed failures to `<failures_log>` and de-duped classes. Note
   which new classes (if any) this round added.
5. **Log** one ledger row (§3) and continue, steering the next round at an untried angle.

**Stop** when `<patience>` consecutive rounds add **no new failure class** (the target has gone dry for
your current repertoire), or at `<budget>`. Report: the catalogue of distinct failure classes with one
reproducible example each, the bypass/over-block split, and — since the goal is a more robust target —
a short suggested fix per class.

---

## 3. Ledger

`<sandbox_root>/ledger.tsv`, tab-separated, never commas in the text. Header:
```
round	angle	tested	new_classes	total_classes
```
Example:
```
round	angle	tested	new_classes	total_classes
0	probe mixed batch	6	case,spacing	2
1	leetspeak + unicode	8	leetspeak	3
2	synonyms + expansions	8	synonym,expansion	5
3	benign trigger substrings	6	overblock	6
4	multi-step phrasing	8	(none)	6
```

---

## 4. Hard constraints
- **Never edit the target, the oracle, or `tools/harness.py`.** They define the system and the
  ground truth; changing them manufactures or hides failures.
- **A failure is an objective target-vs-oracle disagreement** — not your hunch. Every recorded failure
  is reproducible from its input.
- **Label classes honestly and pursue new angles** — the signal is *distinct* failure modes, so do not
  pad counts by relabeling the same technique, and do not stop at the first bypass when others remain.
- Keep findings oriented toward **fixing** the target; this is robustness testing of an authorized system.
- The sandbox is self-contained — no `../` escapes beyond the bound `<sandbox_root>`.
- Do not pause the loop to ask whether to continue; run until it goes dry or hits the budget.
