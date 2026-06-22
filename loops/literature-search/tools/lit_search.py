#!/usr/bin/env python3
"""Entrypoint for the self-contained literature-search helper.

Stdlib only, Python >=3.9 — runs under system python3, the run environment, or
`uv run python` with no installs. Run `python lit_search.py --help`. Source logic
lives in the lit/ package; this just makes it importable regardless of CWD.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lit.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
