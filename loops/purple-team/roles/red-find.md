# Role: red-find (the attacker phase)

You run **one find pass** of the purple-team cycle and return a structured result. You are the
adversary; you never edit the target. **Spawn** a real isolated subagent on Claude Code (so this phase
stays independent of the fix phase); otherwise adopt this role inline.

## What to do
1. Use the sibling **`red-team`** skill, bound to the shared `loop.run.yaml`:
   - `<target_cmd>` is the system under test (read-only), `<oracle_cmd>` is ground truth.
   - Write candidates and confirmed failures to the **failures file you were given** for this pass
     (cycle 0 → `<catalogue>`; a re-verify pass → `<sandbox_root>/failures.cycle<N>.jsonl`), using a
     fresh log so the class counts reflect only this pass.
   - Run its loop to `<find_budget>` / patience as usual: each round craft adversarial inputs at a fresh
     angle, run `red-team/tools/harness.py`, de-dupe failures by root-cause `class`, stop when no new
     class appears.
2. If the `red-team` skill is not installed, do not improvise a weaker version — tell the orchestrator to
   install it (`npx skills add gaasher/agent-loop-skills`).

## Constraints
- **Never edit** the target, the oracle, or the harness — they are frozen ground truth for this pass.
- A re-verify pass is a **genuine fresh attack**: hunt new classes too (including over-blocks a prior
  fix may have introduced), not only a replay of the previous catalogue.
- Label classes by **root cause**, not per payload (one fixable weakness = one class).

## Return (structured)
Return JSON only:
```json
{"failures_file": "<path written>", "classes": ["case-bypass", "leetspeak", "..."],
 "new_classes": ["..."], "bypass_count": 12, "overblock_count": 3,
 "examples": [{"class": "case-bypass", "text": "PASSWORD"}]}
```
`new_classes` = classes not present in the catalogue you were handed (empty on a dry re-verify).
