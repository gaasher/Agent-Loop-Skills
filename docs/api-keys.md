# API key handling (standard for all skills)

Skills that call external APIs (literature search, web synthesis, etc.) all use the
**same key convention** so a user sets each key once and every skill reuses it.

## The shared global key file

```
~/.config/agent-loop-skills/keys.env        (honors $XDG_CONFIG_HOME)
```

- **One file, shared by every skill and project.** Set a key once; all skills see it.
- **Outside any repo**, so it can never be committed. `0600` permissions.
- Plain `KEY=VALUE` lines; `#` comments; blank lines ignored.

```dotenv
# agent-loop-skills API keys (shared across all skills).
S2_API_KEY=xxxxxxxx
OPENALEX_EMAIL=me@example.com
OPENROUTER_API_KEY=
BGPT_API_KEY=
```

## Rules

1. **Precedence:** a real OS environment variable always wins over the file (so CI and
   power users can just `export`). The file fills in whatever the environment doesn't.
2. **All keys optional:** a missing key degrades the corresponding feature gracefully —
   the skill keeps running on whatever is available, down to built-in web search.
3. **Secrets never enter the conversation:** the user fills the file themselves (in
   their editor). Skills only ever read **presence as booleans**, never the values.
4. **One file, many skills:** `--init` *appends* a skill's missing keys to the shared
   file and never overwrites existing values, so skills coexist in one file.

## Onboarding flow (what a skill does at setup)

1. `… keys` — report which keys are already present (the global file may be populated
   from a prior skill). If what you need is there, you're done.
2. `… keys --init` — create the file if absent and append slots for this skill's keys.
   Prints the path.
3. Ask the user to **open the file and paste the keys they want**, then say when done.
   In-session shortcut: `! $EDITOR ~/.config/agent-loop-skills/keys.env`.
4. `… keys` again — report live vs degraded tiers, and proceed. Never block on keys.

## Adopting the standard in a new skill

1. Copy [`../templates/keys.py`](../templates/keys.py) into the skill (e.g. next to its
   helper, or in its package).
2. Edit only the `KEYS` registry — the `(ENV_VAR_NAME, "description — where to get it")`
   list for that skill's services. Leave the engine untouched.
3. In the skill's CLI: default `--env-file` to `keys.default_env_path()`, call
   `keys.load_env_file(args.env_file)` before doing any work, and expose a `keys`
   subcommand that runs `keys.ensure_template(...)` on `--init` and prints
   `keys.status()`.

The engine is standard-library only and Python ≥3.9, so it runs anywhere the skill does
with no installs.
