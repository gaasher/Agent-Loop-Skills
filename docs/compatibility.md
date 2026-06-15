# Host compatibility

> Placeholder — to be confirmed per host as loops are implemented.

All loops follow the Agent Skills standard (`name`, `description`, `metadata.version`),
so they should *install* anywhere skills are supported. What differs across hosts is
**subagent isolation**: whether a loop can spawn a real, isolated subagent, or has to
**degrade** to adopting the role inline in the main context.

| Host | Installs skills | Real subagent isolation | Notes |
| --- | --- | --- | --- |
| Claude Code | ✅ | ✅ | Spawns isolated subagents (the `Agent` tool). |
| Codex | ✅ | ⚠️ TBD | Confirm subagent support. |
| Cursor | ✅ | ⚠️ TBD | Confirm subagent support. |
| Gemini / Antigravity | ✅ | ⚠️ TBD | Confirm subagent support. |
| Hermes | ✅ | ⚠️ TBD | Confirm subagent support. |
| Pi | ✅ | ⚠️ TBD | Confirm subagent support. |

## Spawn-or-degrade

Multi-role loops (critic, evaluator, judge, swarm members…) are written to:

1. **Spawn** a real isolated subagent and hand it the role file plus the resolved
   bindings, where the host supports it; otherwise
2. **Degrade** to reading the role file and adopting the role inline.

This keeps a single loop definition running everywhere, while getting true isolation
(and parallelism) on hosts that offer it.
