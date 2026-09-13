#!/usr/bin/env python3
"""Freeze and hash the confirmatory protocol before any paid execution.

Produces a manifest binding every pre-registered decision to a content hash, so
that (a) the confirmatory analysis provably ran the frozen protocol, and (b)
any later change is detectable rather than silent.

Design notes
------------
* Hashing is over CANONICAL JSON (sorted keys, no insignificant whitespace) so
  the digest is stable across formatting churn.
* Each frozen artifact is hashed individually AND rolled into a single
  `protocol_hash`, mirroring the per-fixture / set-hash pattern the original
  study already used (`persona_set_lock.json`), which was re-verified during
  recovery.
* `verify` recomputes everything and exits non-zero on any drift. Wire this
  into the runner as a hard precondition.
* This script makes NO model calls.

Usage
-----
  freeze_protocol.py freeze --protocol PROTOCOL.md --spec protocol_spec.json \
      --corpus <dir-or-file> ... --code <file> ... --out protocol_lock.json
  freeze_protocol.py verify --lock protocol_lock.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_hash(obj: Any) -> str:
    """Hash of canonical JSON: sorted keys, compact separators, UTF-8.

    Formatting-insensitive by construction, so reindenting the spec does not
    invalidate the freeze but changing a value does.
    """
    return sha256_bytes(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def hash_path(p: Path) -> list[dict[str, str]]:
    """Hash a file, or every file under a directory (sorted, recursive)."""
    if p.is_file():
        return [{"path": str(p), "sha256": sha256_file(p)}]
    entries = []
    for f in sorted(x for x in p.rglob("*") if x.is_file() and x.name != ".DS_Store"):
        entries.append({"path": str(f), "sha256": sha256_file(f)})
    return entries


def set_hash(entries: list[dict[str, str]]) -> str:
    """Order-independent-but-deterministic roll-up of a file set."""
    return canonical_json_hash(sorted(entries, key=lambda e: e["path"]))


def freeze(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.spec).read_text())

    required = [
        "task_corpora", "public_research_prompts", "model_conditions",
        "repetition_counts", "pairwise_estimands", "primary_metrics",
        "property_tolerances", "tolerance_sensitivity_ranges",
        "semantic_matching", "retry_and_exclusion_rules",
        "randomization_procedure", "confirmatory_vs_exploratory",
    ]
    missing = [k for k in required if k not in spec]
    if missing:
        print(f"ERROR: protocol spec missing required sections: {missing}", file=sys.stderr)
        return 2

    sections = {k: canonical_json_hash(spec[k]) for k in sorted(spec)}

    corpora: list[dict[str, str]] = []
    for c in args.corpus or []:
        corpora.extend(hash_path(Path(c)))
    code: list[dict[str, str]] = []
    for c in args.code or []:
        code.extend(hash_path(Path(c)))

    lock: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "frozen_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "status": "FROZEN_PENDING_EXECUTION",
        "protocol_document": {
            "path": str(args.protocol),
            "sha256": sha256_file(Path(args.protocol)),
        },
        "protocol_spec": {
            "path": str(args.spec),
            "sha256": sha256_file(Path(args.spec)),
            "section_hashes": sections,
        },
        "task_corpus_files": corpora,
        "task_corpus_set_hash": set_hash(corpora),
        "analysis_code_files": code,
        "analysis_code_set_hash": set_hash(code),
    }
    # single binding digest over everything above
    lock["protocol_hash"] = canonical_json_hash({
        k: lock[k] for k in (
            "protocol_document", "protocol_spec",
            "task_corpus_set_hash", "analysis_code_set_hash",
        )
    })

    out = Path(args.out)
    out.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "wrote": str(out),
        "protocol_hash": lock["protocol_hash"],
        "corpus_files": len(corpora),
        "code_files": len(code),
    }, indent=2))
    return 0


def verify(args: argparse.Namespace) -> int:
    lock = json.loads(Path(args.lock).read_text())
    problems: list[str] = []
    notes: list[str] = []

    pd = lock["protocol_document"]
    if not Path(pd["path"]).exists():
        problems.append(f"protocol document missing: {pd['path']}")
    elif sha256_file(Path(pd["path"])) != pd["sha256"]:
        problems.append(f"protocol document CHANGED: {pd['path']}")

    ps = lock["protocol_spec"]
    if not Path(ps["path"]).exists():
        problems.append(f"protocol spec missing: {ps['path']}")
    else:
        file_changed = sha256_file(Path(ps["path"])) != ps["sha256"]
        spec = json.loads(Path(ps["path"]).read_text())
        for section, digest in ps["section_hashes"].items():
            if section not in spec:
                problems.append(f"spec section REMOVED: {section}")
            elif canonical_json_hash(spec[section]) != digest:
                problems.append(f"spec section CHANGED: {section}")
        for section in spec:
            if section not in ps["section_hashes"]:
                problems.append(f"spec section ADDED after freeze: {section}")
        # Distinguish a cosmetic reformat (byte hash moved, every section hash
        # intact) from a substantive edit. Both are reported, but only the
        # latter invalidates the freeze.
        if file_changed:
            section_level_problem = any(
                m.startswith("spec section ") for m in problems
            )
            if section_level_problem:
                problems.append(
                    f"protocol spec file CHANGED (substantive): {ps['path']}"
                )
            else:
                notes.append(
                    f"protocol spec file bytes changed but ALL section hashes match "
                    f"({ps['path']}) -- cosmetic reformat only, protocol values intact"
                )

    for label, key, sethash in (
        ("task corpus", "task_corpus_files", "task_corpus_set_hash"),
        ("analysis code", "analysis_code_files", "analysis_code_set_hash"),
    ):
        for e in lock[key]:
            p = Path(e["path"])
            if not p.exists():
                problems.append(f"{label} file missing: {p}")
            elif sha256_file(p) != e["sha256"]:
                problems.append(f"{label} file CHANGED: {p}")
        if set_hash(lock[key]) != lock[sethash]:
            problems.append(f"{label} set hash INCONSISTENT with recorded file list")

    recomputed = canonical_json_hash({
        k: lock[k] for k in (
            "protocol_document", "protocol_spec",
            "task_corpus_set_hash", "analysis_code_set_hash",
        )
    })
    if recomputed != lock.get("protocol_hash"):
        problems.append("top-level protocol_hash INCONSISTENT")

    for n in notes:
        print(f"  NOTE: {n}")
    if problems:
        print("PROTOCOL VERIFICATION: FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PROTOCOL VERIFICATION: PASS")
    print(f"  protocol_hash = {lock['protocol_hash']}")
    print(f"  frozen_at     = {lock['frozen_at']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="freeze-protocol")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("freeze")
    f.add_argument("--protocol", required=True, help="PROTOCOL.md")
    f.add_argument("--spec", required=True, help="machine-readable protocol_spec.json")
    f.add_argument("--corpus", action="append", help="task corpus file or directory (repeatable)")
    f.add_argument("--code", action="append", help="analysis code file or directory (repeatable)")
    f.add_argument("--out", required=True)
    f.set_defaults(fn=freeze)

    v = sub.add_parser("verify")
    v.add_argument("--lock", required=True)
    v.set_defaults(fn=verify)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
