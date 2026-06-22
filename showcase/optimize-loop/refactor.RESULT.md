# codeRefactorLoop — sandbox run (Sonnet, 2026-06-21)

Runner: Sonnet subagent, budget=6, patience=3.
Result: complexity 23 -> 15 (-35%), max_nesting 7 -> 3, loc 86 -> 45. 13/13 tests green.
6 iterations, 5 keeps + 1 correct discard (iter6 raised complexity).
Skill fix applied from this run: made the keep/discard tie-break an explicit lexicographic
(complexity, max_nesting, loc) comparison with worked examples.

Files: ledger.tsv, messy_stats.baseline.py (input), messy_stats.refactored.py (output).
