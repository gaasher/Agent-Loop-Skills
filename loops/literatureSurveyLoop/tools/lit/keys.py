"""Standardized API-key handling for agent-loop-skills.

Keys live in one file at the PROJECT ROOT — ``<repo root>/keys.env`` (the nearest .git
ancestor of the working directory, else the CWD) — shared by every skill in that
project. It MUST be gitignored (it sits inside the repo). Real OS env vars take
precedence over the file.

This module is a drop-in standard: the ENGINE below is identical across skills; each
skill edits only the KEYS registry. status() reports presence as booleans only — never
the values — so onboarding never puts a secret in the conversation.

See docs/api-keys.md for the full convention.
"""

import os

# === per-skill registry: edit ONLY this list when copying into another skill ==========
# (env var name, "verbose description: cost · what it enables · consequence if missing · where to get it")
KEYS = [
    ("S2_API_KEY",
     "Semantic Scholar | FREE, STRONGLY RECOMMENDED — the one key this loop wants. Enables "
     "reliable semantic (SPECTER2) paper search, full-text snippet search, and "
     "citation-graph traversal at 1 req/s — the three retrieval primitives ScholarEval is "
     "built on. Without it: S2 falls back to a saturated global shared pool (frequent "
     "429s), and the loop leans harder on arXiv full-text + your built-in WebSearch/"
     "WebFetch. Get one: https://www.semanticscholar.org/product/api#api-key-form"),
]

# === generic engine: identical across skills — do not edit ============================
_HEADER = [
    "# agent-loop-skills API keys (shared across skills in this project).",
    "# Fill in the ones you want; blank/missing means that source degrades gracefully.",
    "# Real environment variables override this file. KEEP THIS GITIGNORED.",
    "",
]


def default_env_path():
    """The project key file: keys.env at the nearest .git ancestor of the CWD, else CWD."""
    d = os.getcwd()
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return os.path.join(d, "keys.env")
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.join(os.getcwd(), "keys.env")
        d = parent


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


def report():
    """Per-key detail for an at-a-glance note: each key's presence + what it gates,
    plus live/missing lists. Values are never included."""
    present = status()
    keys_detail = {name: {"present": present[name], "info": desc} for name, desc in KEYS}
    return {
        "keys": keys_detail,
        "live": [n for n, v in keys_detail.items() if v["present"]],
        "missing": [n for n, v in keys_detail.items() if not v["present"]],
    }


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
