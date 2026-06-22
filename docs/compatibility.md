# Host compatibility

All loops follow the Agent Skills standard (`name` == folder name, `description`, `metadata.version`),
so they *install* anywhere skills are supported. What differs across hosts is **subagent isolation**:
whether a loop can spawn a real, isolated subagent, or has to **degrade** to adopting the role inline in
the main context.

| Host | Installs skills | Real subagent isolation | Notes |
| --- | --- | --- | --- |
| Claude Code | ✅ | ✅ | Spawns isolated subagents (the `Agent` / Task tool). |
| Codex | ✅ | ⚠️ TBD | Confirm subagent support. |
| Cursor | ✅ | ⚠️ TBD | Confirm subagent support. |
| Gemini / Antigravity | ✅ | ⚠️ TBD | Confirm subagent support. |
| Hermes | ✅ | ⚠️ TBD | Confirm subagent support. |
| Pi | ✅ | ⚠️ TBD | Confirm subagent support. |

`TBD` means the host installs skills fine but real subagent isolation is unconfirmed — loops degrade to
inline roles there until it's verified.

## Spawn-or-degrade

Multi-role loops (critic, evaluator, judge, swarm members…) are written to:

1. **Spawn** a real isolated subagent and hand it the role file (`roles/*.md`) plus the resolved
   bindings, where the host supports it; otherwise
2. **Degrade** to reading the role file and adopting the role inline.

Detect the host once (is `AskUserQuestion` available? → Claude Code) and branch. This keeps one loop
definition running everywhere, while getting true isolation (and parallelism) on hosts that offer it.
See the authoring contract in
[`skill-authoring-rules.md`](skill-authoring-rules.md#roles-and-spawn-or-degrade).
