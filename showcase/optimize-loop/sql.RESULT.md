# sqlOptimizeLoop — sandbox run (Sonnet, 2026-06-21)

Runner: Sonnet subagent, budget=6, patience=3. DB: 1500 customers / 30000 orders.
Result: median 1131.75 ms -> 1.055 ms (~1073x). Result-set hash matched baseline every
kept iteration (correctness preserved). 3 keeps + 3 correct discards.
Wins: decorrelate subquery -> JOIN+GROUP BY (~200x), composite index orders(customer_id,
amount), pre-aggregate before join.
Skill fix from this run: made the plateau/patience counting rule explicit (every
non-improving iteration counts; reset on keep).

Files: ledger.tsv, query.baseline.sql (input), query.optimized.sql + indexes.optimized.sql (output).
