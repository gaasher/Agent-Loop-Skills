# agent-loop-skills

> `while (!done) loop()` — drop-in agentic loops (autoresearch, writing, brainstorming)
> for Claude Code, Codex & any Agent Skills host.

A library of **plug-and-play agentic loop templates** that drop into any Agent Skills
host — Claude Code, Codex, Cursor, Gemini/Antigravity, Hermes, Pi.

Instead of task-specific skills, each entry is a *generic, reusable loop* — autoresearch,
document writing, brainstorming, data work — that you bind to **your own task at invocation
time**. The design priority is **ease of use, reach, and plug-and-play integration** over
task-specificity.

## How a loop works

Every loop decomposes into five ingredients:

1. **Program** — the orchestration instructions (`SKILL.md`).
2. **Artifact slot** — the thing being improved (a model, a document, a dataset…).
3. **Feedback signal** — the score/critique that drives the next step.
4. **Run ledger** — an append-only log of what changed and why.
5. **Termination / budget** — when to stop.

The `SKILL.md` is the wrapper: it **resolves your bindings** (conversationally, or from a
`loop.run.yaml`), then runs the program. Loops with sub-roles use a **spawn-or-degrade**
pattern: they spawn a real isolated subagent where the host supports it, and otherwise adopt
the role inline. Skills ship **zero heavy dependencies** — your own code (a torch trainer, a
SQL database, a dataset) runs in *your* environment via a bound run command; the skill only
shells out to it and reads the result.

## Install

> One command — copies every loop into your local Agent Skills directory.

```bash
git clone https://github.com/gaasher/agent-loop-skills && \
  cp -r agent-loop-skills/loops/* ~/.claude/skills/
```

Several research loops call the shared **`literature-search`** skill; installing everything
(as above) puts it alongside them. Any loop degrades gracefully (to WebSearch) if it is absent.
*(Adjust the destination for your host.)*

## Loops

**Autoresearch — iterate on an ML artifact against a metric**

| Loop | What it does |
| --- | --- |
| [`karpathy`](loops/karpathy) | The minimal baseline: propose a change, run training, keep it if the metric improved, else revert. |
| [`ml-autoresearch`](loops/ml-autoresearch) | Analysis-first: diagnoses each run (gradients, activations, errors…) and grounds the next change in the evidence. A `literature` dial adds paper-grounded changes. |
| [`exploratory-autoresearch`](loops/exploratory-autoresearch) | Forces broad exploration via a temperature/swing scheduler with a stagnation guard, so it doesn't hill-climb one idea forever. |
| [`tournament-autoresearch`](loops/tournament-autoresearch) | Agents pitch competing changes; a self-calibrating judge runs deliberation rounds and picks one per step. |
| [`dueling-autoresearch`](loops/dueling-autoresearch) | Two approaches race the same metric in parallel and borrow ideas across lanes. |
| [`alpha-evolve`](loops/alpha-evolve) | Population-based evolution (MAP-Elites + islands, diff-mutate, cascade-eval). |

**Literature & writing**

| Loop | What it does |
| --- | --- |
| [`literature-search`](loops/literature-search) | Shared toolchain (not a loop): paper discovery, snippets, citation-graph, full-text over Semantic Scholar + arXiv. The other research loops call it. |
| [`literature-survey`](loops/literature-survey) | Builds a saturating evidence/contradiction matrix of sources × claims on a question. |
| [`research-question`](loops/research-question) | Sharpens a vague topic into strong, novel, feasible research questions. |
| [`hypothesis-gen`](loops/hypothesis-gen) | Generates and literature-vets a pool of research hypotheses. |
| [`research-proposal`](loops/research-proposal) | Grades a proposal against the literature (ScholarEval) and revises until it clears a passing grade. |
| [`scientific-writer`](loops/scientific-writer) | Specialist judges + an independent peer-reviewer critique a draft; a writer revises prose/figures/code until the score clears a threshold. |

**Data**

| Loop | What it does |
| --- | --- |
| [`data-analysis`](loops/data-analysis) | Hypothesis → verify discovery; every finding is backed by a reproduced number at a meaningful effect size. |
| [`anomaly-investigation`](loops/anomaly-investigation) | Diagnoses the cause of a known anomaly by forming, testing, and eliminating candidates. |
| [`claim-verify`](loops/claim-verify) | Adversarially verifies the claims in a results draft against the underlying data before publishing. |
| [`tabular-cleanup`](loops/tabular-cleanup) | Cleans a messy table to an inferred data contract with deterministic pass/fail checks. |

**Code & optimization**

| Loop | What it does |
| --- | --- |
| [`optimize-loop`](loops/optimize-loop) | Evaluator-optimizer with a pluggable correctness gate + minimized metric — refactor code under test (tests green + complexity↓) or speed up a SQL query (identical results + latency↓). |
| [`prompt-optimize`](loops/prompt-optimize) | Evolves a prompt against a user-supplied scoring command (a black-box oracle). |

**Other**

| Loop | What it does |
| --- | --- |
| [`red-team`](loops/red-team) | Adversarial loop-until-dry that surfaces distinct failure classes of a system you own (authorized robustness testing). |
| [`power-analysis`](loops/power-analysis) | Sizes and preregisters a two-arm experiment to hit a target statistical power. |

## Provenance / credits

- [`karpathy`](loops/karpathy) — a faithful adaptation of Andrej Karpathy's
  [autoresearch](https://github.com/karpathy/nanochat) program-as-skill idea.
- [`alpha-evolve`](loops/alpha-evolve) — a simplified, ML-bent re-creation of **AlphaEvolve**
  (A. Novikov et al., 2025, [arXiv:2506.13131](https://arxiv.org/abs/2506.13131)) and its
  open-source implementation
  [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve).
- [`research-proposal`](loops/research-proposal) — its ScholarEval evaluator is a faithful
  reimplementation of **ScholarEval** ([arXiv:2510.16234](https://arxiv.org/abs/2510.16234)).
- Overall layout and the dependency-isolation philosophy are informed by the
  [K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) library.

## Repo layout

```
agent-loop-skills/
├── README.md
├── loops/                 # one self-contained, installable skill per folder (SKILL.md + 5 subfolders)
└── docs/
    ├── skill-authoring-rules.md   # the rubric every loop is written against
    ├── authoring.md               # quick start for writing a new loop
    ├── api-keys.md                # the shared keys.env convention (authoring reference)
    └── compatibility.md           # which hosts get real subagent isolation vs. inline fallback
```

Each loop is a self-contained folder: a single `SKILL.md` plus any of `tools/ roles/ schemas/
rubrics/ examples/`. See [`docs/skill-authoring-rules.md`](docs/skill-authoring-rules.md) for the
authoring contract.
