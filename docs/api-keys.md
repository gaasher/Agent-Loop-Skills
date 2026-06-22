# API key handling (the shared convention)

Skills that call external APIs (literature search, web synthesis, …) all use the **same key convention**
so a user sets each key once and every skill in the project reuses it.

This page is the **authoring reference**. The **installed reference implementation** is the
[`literature-search`](../loops/literature-search) skill (`tools/lit/keys.py`), and its `SKILL.md`
documents the convention for runtime. Consuming skills reach it through that sibling skill
(`<lit> keys` / `<lit> keys --init`) — an installed `SKILL.md` never links `docs/` (it isn't installed).

## The project key file

```
<repo root>/keys.env        (nearest .git ancestor of the working dir, else the CWD)
```

- **One file per project, shared by every skill in it.** Set a key once; all skills see it.
- **Sits inside the repo, so it MUST be gitignored** (`keys.env`). `0600` permissions.
- Plain `KEY=VALUE` lines; `#` comments; blank lines ignored.

```dotenv
# agent-loop-skills API keys (shared across skills in this project).
S2_API_KEY=xxxxxxxx
OPENALEX_EMAIL=me@example.com
OPENROUTER_API_KEY=
BGPT_API_KEY=
```

## Rules

1. **Precedence:** a real OS environment variable always wins over the file (so CI and power users can
   just `export`). The file fills in whatever the environment doesn't.
2. **All keys optional:** a missing key degrades the corresponding feature gracefully — the skill keeps
   running on whatever is available, down to built-in web search.
3. **Secrets never enter the conversation:** the user fills the file themselves (in their editor).
   Skills only ever read **presence as booleans**, never the values.
4. **One file, many skills:** `--init` *appends* a skill's missing keys to the shared file and never
   overwrites existing values, so skills coexist in one file.

## Onboarding flow (what a skill does at setup)

The `literature-search` skill exposes this as `<lit> keys [--init]`; a skill with its own keys mirrors it:

1. `… keys` — report which keys are already present (the shared file may be populated by a prior skill).
   If what you need is there, you're done.
2. `… keys --init` — create the file if absent and append slots for this skill's keys. Prints the path.
3. Ask the user to **open the file and paste the keys they want**, then say when done. In-session
   shortcut: `! $EDITOR ./keys.env`.
4. `… keys` again — report live vs degraded tiers, and proceed. Never block on keys.

## Adopting the convention in a new skill

1. Copy the reference implementation
   [`../loops/literature-search/tools/lit/keys.py`](../loops/literature-search/tools/lit/keys.py) into
   the new skill's `tools/`.
2. Edit only the `KEYS` registry — the `(ENV_VAR_NAME, "description — where to get it")` list for that
   skill's services. Leave the engine untouched.
3. In the skill's CLI: default `--env-file` to `keys.default_env_path()`, call
   `keys.load_env_file(args.env_file)` before doing any work, and expose a `keys` subcommand that runs
   `keys.ensure_template(...)` on `--init` and prints `keys.status()`.

The engine is standard-library only and Python ≥3.9, so it runs anywhere the skill does with no installs.
