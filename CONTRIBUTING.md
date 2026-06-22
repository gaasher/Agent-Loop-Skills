# Contributing to agent-loop-skills 🎉

First off — **thank you for being here.** This project gets better every single time someone adds a loop,
sharpens a description, files a bug, or shares how they used one. I love open source, and this repo is built
to be added to.

**You don't need to be an expert, and you don't need to write code.** Docs, examples, run transcripts, and
good bug reports are first-class contributions — about a quarter of open-source contributions are
documentation, and they matter just as much. Be kind, assume good faith, and have fun.

## Ways to contribute

- 🧩 **Add a loop** — a new generic, reusable agentic loop.
- 🛠 **Improve a loop** — tighten a `SKILL.md`, fix a tool, sharpen a `description`.
- 📚 **Docs & examples** — clarify the rules, add a "loop in action" transcript to `showcase/`.
- 🐛 **Report a bug** — what you ran, what you expected, what happened (host + loop + transcript).
- 💡 **Float an idea** — open a discussion or issue; half-formed is fine.

## Your first contribution

New here? Look for [`good first issue`](https://github.com/gaasher/agent-loop-skills/labels/good%20first%20issue)
(small and well-scoped) and [`help wanted`](https://github.com/gaasher/agent-loop-skills/labels/help%20wanted).
Comment to claim one — I'm happy to help you land it. The [Roadmap](README.md#roadmap) is also fair game
(e.g. the blue-teaming + communication interface).

## Adding a loop

1. Read **[`docs/skill-authoring-rules.md`](docs/skill-authoring-rules.md)** — the rubric every loop ships
   against (it's short and opinionated on purpose).
2. Copy the skeleton in **[`docs/authoring.md`](docs/authoring.md)** into `loops/<your-loop>/SKILL.md`.
3. Build it as a real loop — the **five ingredients**: program, artifact slot, feedback signal, run ledger,
   termination/budget.
4. Run it once against a small `sandbox/` case with **Sonnet**, and iterate the skill from what you observe.
5. Run the checklist below, then open a PR.

### Skill submission checklist

- [ ] **One job.** A single, generic, reusable loop — not five tasks bundled together.
- [ ] **All five ingredients** present: program · artifact slot · feedback signal · run ledger · termination/budget.
- [ ] **Folder name == frontmatter `name`** (lowercase-hyphen, ≤64 chars, no `claude`/`anthropic`).
- [ ] **Strong `description`** (≤1024 chars): leads with `Use when…` triggers + a brief what-it-does + a negative trigger. (Bad: *"Helps with data."*)
- [ ] **`SKILL.md` < ~500 lines**; detail pushed into `tools/ roles/ schemas/ rubrics/ examples/`; references one level deep.
- [ ] **Self-contained:** no `../` escapes, no runtime links to `docs/`.
- [ ] **Objective, locally-runnable feedback signal** wherever possible (tests, a metric, a hash, a calibrated judge).
- [ ] **Spawn-or-degrade** for any sub-role (real subagent where supported, inline otherwise).
- [ ] **Tools are stdlib-only**, 3.9-safe, with deferred heavy imports. No bundled dependencies.
- [ ] **No secrets** — keys go through the shared `keys.env` convention ([`docs/api-keys.md`](docs/api-keys.md)).
- [ ] **`metadata.version`** present (quoted); bump it when editing an existing loop.
- [ ] **Tested with Sonnet** against a `sandbox/` case — **paste the run** in the PR (ledger moving the right way + the final artifact passing its check).
- [ ] **Root README updated** — the loop table (+ a `†` if multi-role), and provenance/credits if you're adapting prior work.

## PR workflow

- **Fork & branch.** One loop or one fix per PR — small PRs get merged faster.
- **Clear commits:** `feat(loop): add <name>`, `fix(<loop>): …`, `docs: …`.
- **Fill in the PR description.** For a new or changed loop, include the Sonnet run transcript (the ledger +
  the final result) — that's the single most useful thing a reviewer can see.
- **CI / checks** should be green (layout, JSON/Python validity).

## What reviewers look for

A valid open-standard skill, a crisp `Use when…` description, a **real transcript** that shows the signal
moving the right way, no secrets, and *one job done well*. Expect first-pass feedback within a few days — if
I go quiet, ping the PR, I don't bite.

## Be excellent to each other

Be respectful and welcoming — harassment or unkindness isn't tolerated. We follow the spirit of the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). If something feels
off, open an issue or reach out to the maintainer.

Thanks again for contributing — every loop counts. 💜
