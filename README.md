# agent-loop-skills

> `while (!done) loop()` — drop-in agentic loops (autoresearch, writing, brainstorming)
> for Claude Code, Codex & any Agent Skills host.

A library of **plug-and-play agentic loop templates** that drop into any Agent Skills
host — Claude Code, Codex, Cursor, Gemini/Antigravity, Hermes, Pi.

Instead of task-specific skills, each entry is a *generic, reusable loop* —
autoresearch, document writing, brainstorming, deep research — that you bind to
**your own task at invocation time**. Inspired by
[`karpathy/autoresearch`](https://github.com/karpathy) (program-as-skill) and the
K-Dense scientific-agent-skills layout, but templating *loops* rather than fixed tasks.

The design priority is **ease of use, reach, and plug-and-play integration** over
task-specificity.

## How a loop works

Every loop decomposes into five ingredients:

1. **Program** — the orchestration instructions.
2. **Artifact slot** — the thing being improved (a model, a document, a dataset…).
3. **Feedback signal** — the score/critique that drives the next step.
4. **Run ledger** — an append-only log of what changed and why.
5. **Termination / budget** — when to stop.

The `SKILL.md` is the wrapper: it **resolves your bindings** (conversationally, or
from a `loop.run.yaml`), then runs the program. Loops with sub-roles use a
**spawn-or-degrade** pattern: they spawn a real isolated subagent where the host
supports it, and otherwise adopt the role inline.

## Install

> One command — copies every loop into your local Agent Skills directory.

```bash
git clone https://github.com/gaasher/agent-loop-skills && \
  cp -r agent-loop-skills/loops/* ~/.claude/skills/
```

*(Adjust the destination for your host — see [`docs/compatibility.md`](docs/compatibility.md).)*

## Loops

| Loop | What it does |
| --- | --- |
| [`karpathy`](loops/karpathy) | Default single-agent iterate-and-score loop, fully inline. |
| [`standardMLAutoresearch`](loops/standardMLAutoresearch) | Simple mono-agent ML research loop. |
| [`highTemperatureMLAutoresearch`](loops/highTemperatureMLAutoresearch) | Mono-agent loop that pivots hard when it detects hill-climbing. |
| [`multiAgentMLAutoresearch`](loops/multiAgentMLAutoresearch) | Subagents propose under a schema; a parent agent filters. |
| [`deepAgentMLAutoresearch`](loops/deepAgentMLAutoresearch) | Standard loop with arXiv MCP access for grounded research. |
| [`MLAutoresearchSwarm`](loops/MLAutoresearchSwarm) | A swarm of autoresearch agents running in parallel. |
| [`duelingMLAutoresearch`](loops/duelingMLAutoresearch) | Classical vs. learned approaches battle in parallel and compare notes. |
| [`adversarialMLAutoResearch`](loops/adversarialMLAutoResearch) | Agents pitch theses; a judge runs deliberation rounds before each step. |
| [`scientificWriterLoop`](loops/scientificWriterLoop) | Five specialist judges (figures, science, style, formatting, code) critique a draft; an independent peer_reviewer grades it; a writer revises prose/figures/code until the score clears a threshold. |
| [`tabularCleanupLoop`](loops/tabularCleanupLoop) | Single agent iteratively cleans tabular data. |
| [`researchProposalLoop`](loops/researchProposalLoop) | ScholarEval grades a research proposal against the literature; a Judge scores the feedback and a Reviser iterates until it clears a passing grade. |

## Repo layout

```
agent-loop-skills/
├── README.md
├── loops/                 # one self-contained, installable loop per folder
├── templates/             # OPTIONAL authoring starters — never referenced at runtime
└── docs/
    ├── authoring.md       # how to write a new loop
    └── compatibility.md   # which hosts get real subagent isolation vs. inline fallback
```

## Status

Scaffold stage — folders and READMEs are in place; the loop programs are not yet
implemented. See each loop's README for its intended behavior.
