# Host compatibility

Every loop is an open-standard [`SKILL.md`](https://agentskills.io/specification) (`name` == folder,
`description`, `metadata.version`), so it **installs** on any Agent-Skills host. Two capabilities matter,
and they have **different** support:

1. **Skills** — a `SKILL.md` the model discovers and invokes on its own (progressive disclosure).
   Broadly supported across the open standard.
2. **Loop-dispatched subagents** — a loop, mid-run, handing an **arbitrary `roles/*.md` file** to an
   **isolated subagent** at runtime (the "spawn" half of [spawn-or-degrade](#spawn-or-degrade)).
   Confirmed only on Claude Code.

| Host | Skills (model-invoked) | Loop-dispatched subagents | Source |
| --- | --- | --- | --- |
| **Claude Code** | ✅ | ✅ real, isolated, parallel (Task tool) | **verified here** + [docs](https://code.claude.com/docs/en/skills), [sub-agents](https://code.claude.com/docs/en/sub-agents) |
| Claude Agent SDK | ✅ | ✅ `AgentDefinition` + Agent tool | [docs](https://code.claude.com/docs/en/agent-sdk/subagents) |
| Codex CLI | ✅ (`.agents/skills/`) | ➖ inline | [skills](https://developers.openai.com/codex/skills) · [subagents](https://developers.openai.com/codex/subagents) |
| Cursor | ✅ (`.cursor/` or `.agents/skills/`) | ➖ inline | [skills](https://cursor.com/docs/skills) · [2.4](https://cursor.com/changelog/2-4) |
| Hermes (Nous) | ✅ | ➖ inline | host docs (unverified by us) |
| Antigravity · Pi · OpenClaw · NVIDIA NemoClaw | ✅ *(reported)* | ➖ inline | open standard; **not verified by us** |

Legend: ✅ verified/official · ➖ inline fallback (runs, no isolation) · *(reported)* = adopts the open
standard but we haven't tested it. Single-agent loops run fully everywhere; `tools/` (stdlib Python) and
the shared `keys.env` work on any host with a shell.

## Why subagents are Claude-Code-only (the precise reason)

The blocker off Claude Code is **not** "can the host spawn subagents" — most can. It's that they require
subagents to be **pre-registered** and/or triggered by an **explicit user action**, whereas our loops
need to hand an **arbitrary role file to a subagent at runtime**:

- **Codex** — subagents are pre-defined TOML in `~/.codex/agents/`, and *"Codex only spawns a new agent
  when you explicitly ask it to."* Skill-body instructions to spawn are not honored as that ask
  ([openai/codex#23496](https://github.com/openai/codex/issues/23496)).
- **Cursor** — the main agent auto-delegates only to **pre-registered** subagents (chosen by their
  descriptions); the skills docs state a skill has no capability to create child agents.
- **Hermes** — has an agent-callable `delegate_task()` that *could* spawn, but not from our role-file
  pattern, and we haven't verified it.

"A skill is just a prompt loaded into context" doesn't change this — the runtime, ad-hoc role dispatch
our multi-role loops use is the Task tool, which is Claude-Code-specific. **So: off Claude Code, do not
rely on loop-dispatched subagents or parallelism — the multi-role loops run their roles inline (serial),
which is correct, just slower.**

## Spawn-or-degrade

Multi-role loops (judge / critic / mutator / reviser / track agents) are written to:

1. **Spawn** a real isolated subagent and hand it the role file (`roles/*.md`) + the resolved bindings,
   where the host supports it (Claude Code); otherwise
2. **Degrade** to reading the role file and adopting the role inline in the same context.

The loop detects the host once (is `AskUserQuestion`/the Task tool available? → Claude Code) and branches.
This keeps one loop definition running everywhere while getting true isolation (and parallelism) where
offered. See the authoring contract in
[`skill-authoring-rules.md`](skill-authoring-rules.md#roles-and-spawn-or-degrade).

## If you want real isolation on another host (future work — not implemented)

Each host *could* be adapted with a host-specific dispatch path — Hermes `delegate_task()`, Cursor
pre-registered subagents, an Antigravity manager flow — by teaching a loop's host-detection to target it.
We have **not** built these and do **not** claim them; the loops degrade to inline there today.

## Install paths

No single universal dir. Claude Code reads `~/.claude/skills/`; the other open-standard hosts read the
cross-tool `~/.agents/skills/` (Hermes uses `hermes skills tap add`). The standard installers
(`npx skills add`, `gh skill install --agent <host>`) place skills in the right dir automatically. `name`
must equal the folder name (Cursor and the spec enforce it — every loop here complies). See the README
[Install](../README.md#install) section for the exact commands.
