"""Load KEY=VALUE pairs from a .env file into os.environ.

Tolerant of comments, blank lines, `export` prefixes, quotes, and values
containing '='. Shell `source` aborts the whole file on one malformed line and
silently leaves later variables unset — which produced a confusing 401 during
bring-up — so the loader is explicit instead.

Never prints a value.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path, override: bool = False) -> list[str]:
    loaded = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key or (key in os.environ and not override):
            continue
        os.environ[key] = val
        loaded.append(key)
    return loaded
