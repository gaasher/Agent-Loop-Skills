# redTeamLoop — sandbox run (Sonnet, 2026-06-21)

Target: guardrail.py (naive content filter). Oracle: oracle.py (ground-truth policy).
Runner: Sonnet, budget=8, patience=2. adversarial loop-until-dry; signal = distinct failure classes.
Result: surfaced ALL 5 planted weaknesses (root causes):
  1. case-insensitive bypass   2. missing synonyms/expansions   3. no leetspeak normalization
  4. no spacing/punctuation normalization   5. over-broad "secret" -> over-block (false positives)
39 bypasses + 6 over-blocks. Gave a one-line fix per root cause.
Caveat observed: the agent labeled classes at technique x payload granularity (45 labels) so the
loop never went dry (budget stopped it). Skill fixed: a `class` is the root-cause technique, not
one-per-payload — keeps the dry-stop meaningful.
