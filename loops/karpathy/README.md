# karpathy

**The default loop: single-agent iterate-and-score, fully inline.**

A faithful take on the `karpathy/autoresearch` program-as-skill pattern. One agent
runs the whole loop with no subagents — everything lives in `SKILL.md`. Each
iteration it proposes a change to the `<artifact>`, runs it, scores it against the
`<objective>`, then keeps or reverts and logs the outcome to the `<ledger>`. Repeats
until `<budget>` is hit.

Start here if you want the simplest possible autoresearch loop.

> Scaffold only — program not yet implemented.
