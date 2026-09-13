#!/usr/bin/env python3
"""Build the reviewer release archive.

Explicit allow-by-walk with a deny list: excludes VCS, caches, venvs, logs,
credentials and the non-redistributable raw ContractNLI files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STEM = "variance-aware-llm-migration-tse-artifact"

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache",
                ".mypy_cache", ".venv", "venv", "env", ".idea", ".vscode",
                ".ipynb_checkpoints", ".DS_Store", "node_modules", "htmlcov"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp", ".orig",
                  ".rej", ".coverage"}
EXCLUDE_NAMES = {".DS_Store", ".env", "vaml.env", ".replication.env",
                 ".coverage", "credentials.json", "token.json"}
# Raw dataset: referenced by hash, never redistributed.
EXCLUDE_PREFIXES = ("data/raw/contractnli/",)


def excluded(rel: Path) -> str | None:
    parts = rel.parts
    for p in parts[:-1]:
        if p in EXCLUDE_DIRS:
            return f"dir:{p}"
    if parts[-1] in EXCLUDE_DIRS or rel.name in EXCLUDE_NAMES:
        return "name"
    if rel.suffix in EXCLUDE_SUFFIX:
        return f"suffix:{rel.suffix}"
    s = rel.as_posix()
    for pre in EXCLUDE_PREFIXES:
        if s.startswith(pre):
            return f"prefix:{pre}"
    if ".pre_" in rel.name:
        return "ledger-backup"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=REPO / "dist")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{STEM}.zip"

    included, skipped = [], {}
    for p in sorted(REPO.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(REPO)
        if rel.as_posix().startswith("dist/"):
            continue
        why = excluded(rel)
        if why:
            skipped.setdefault(why, []).append(rel.as_posix())
        else:
            included.append(rel)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in included:
            z.write(REPO / rel, f"{STEM}/{rel.as_posix()}")

    h = hashlib.sha256(out.read_bytes()).hexdigest()
    (args.out_dir / f"{STEM}.zip.sha256").write_text(f"{h}  {out.name}\n")
    print(json.dumps({
        "archive": str(out), "sha256": h,
        "size_mb": round(out.stat().st_size / 1e6, 2),
        "files_included": len(included),
        "files_skipped": sum(len(v) for v in skipped.values()),
        "skip_reasons": {k: len(v) for k, v in sorted(skipped.items())},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
