# duelingMLAutoresearch

**Two approaches raced head-to-head on the same task — and they learn from each other.**

Two tracks work the same objective in parallel — by default a **classical/algorithmic** lane and
an **ML/learned** lane (you name them at setup, so it fits any A-vs-B duel: gradient-boosting vs
deep net, feature-engineering vs end-to-end, …). Each track runs the
[`standardMLAutoresearch`](../standardMLAutoresearch) analysis-first loop in its own lane and
sandbox. The duel is motivated by a recurring lesson: classical methods are often surprisingly
strong, and a head-to-head keeps the loop honest about what actually wins.

How it works:

- **Two lanes, one objective.** Both optimize the **same `<metric>` on the same eval** — that
  shared ground truth is what makes the scoreboard meaningful.
- **They communicate.** Each round, both tracks post to a shared `duel_log.md` — best score, a key
  finding, a dead end, and one idea the other lane could borrow — and read it before their next move.
- **Borrow, but stay in lane.** A track may adapt an *idea or component* from the other (the
  learned lane borrows a hand-crafted feature; the classical lane borrows an augmentation), but it
  never converts into the other approach. That preserves the contest.
- **Honest head-to-head.** An orchestrator advances both tracks each round (in parallel where the
  host supports subagents, else sequentially) and keeps a running scoreboard + current leader — it
  reports the leader, never a final victory.

## Files

| File | Role |
| --- | --- |
| [`SKILL.md`](SKILL.md) | The program — setup + the duel loop (the orchestrator). |
| [`roles/TrackAgent.md`](roles/TrackAgent.md) | The per-track researcher, instantiated once per lane. |
| [`schema.example.yaml`](schema.example.yaml) | Example resolved bindings (shared + the two lanes). |

## Note on the lanes (and where their code lives)

Each lane has a **code location** — and **no code is ever added to the codebase**:

- **`codebase`** — the lane edits existing repo files and runs an existing entrypoint
  (e.g. the learned lane edits `model.py`/`config.yaml` and runs `train.py`).
- **`sandbox`** — the lane authors and runs its code entirely inside
  `<sandbox_root>/<lane>/iter<N>/` (e.g. the classical lane builds itself in the sandbox). The kept
  iteration carries forward as the next one's starting point.

So on a repo that ships a single model (like the testbed's `train.py`), you can run a real
classical-vs-learned duel with the **learned lane = `codebase`** and the **classical lane =
`sandbox`** — the classical approach is built up in the sandbox, leaving the codebase untouched.
Both lanes must still report the same `<metric>` on the same eval. For a single-approach research
loop, use [`standardMLAutoresearch`](../standardMLAutoresearch).
