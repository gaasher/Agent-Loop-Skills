"""Standard API-key handling for agent-loop-skills — DROP-IN TEMPLATE.

Copy this file into any skill that needs API keys. Edit ONLY the KEYS registry below;
leave the engine unchanged. All skills then share one global key file:

    ${XDG_CONFIG_HOME:-~/.config}/agent-loop-skills/keys.env

It lives outside any repo (can't be committed), real OS env vars take precedence over
it, and status() reports presence as booleans only — never the values — so onboarding
never puts a secret in the conversation. See docs/api-keys.md for the convention.

Wire-up in the skill's CLI:
  - default --env-file to keys.default_env_path()
  - call keys.load_env_file(args.env_file) before doing any work
  - add a `keys` subcommand: on --init call keys.ensure_template(path); print keys.status()
"""

import os

# === per-skill registry: edit ONLY this list ==========================================
# (env var name, "human description — where to get it")
KEYS = [
    ("EXAMPLE_API_KEY", "Example service (free/paid) — https://example.com/get-a-key"),
    # ("ANOTHER_KEY", "Another service — https://..."),
]

# === generic engine: identical across skills — do not edit ============================
_HEADER = [
    "# agent-loop-skills API keys (shared across all skills).",
    "# Fill in the ones you want; blank/missing means that source degrades gracefully.",
    "# Real environment variables override this file.",
    "",
]


def default_env_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "agent-loop-skills", "keys.env")


def load_env_file(path=None):
    """Load KEY=VALUE lines into os.environ. Real env vars win (setdefault)."""
    path = path or default_env_path()
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v:
                os.environ.setdefault(k, v)


def status(names=None):
    """Which keys are present — booleans only, never the values."""
    names = names or [name for name, _ in KEYS]
    return {name: bool(os.environ.get(name)) for name in names}


def _present_names(text):
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            out.add(line.split("=", 1)[0].strip())
    return out


def ensure_template(path=None):
    """Create the shared key file if absent, and APPEND any of this skill's keys that
    aren't already in it. Never overwrites existing values — so multiple skills can
    share one file. Returns the path."""
    path = path or default_env_path()
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
    have = _present_names(existing)
    to_add = [(n, d) for n, d in KEYS if n not in have]
    if existing and not to_add:
        return path

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    chunk = [] if existing else list(_HEADER)
    for name, desc in to_add:
        chunk += ["# " + desc, "{}=".format(name), ""]
    with open(path, "a" if existing else "w", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("\n".join(chunk))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
