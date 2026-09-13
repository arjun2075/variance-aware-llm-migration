#!/usr/bin/env python3
"""Hard precondition for the confirmatory run. Refuses to pass on placeholders.

Blocks launch if:
  * the P2 corpus is synthetic fixtures rather than real ContractNLI;
  * the ContractNLI validation report is missing or FAIL;
  * the protocol lock does not verify;
  * the Git working tree is dirty;
  * corpus counts do not match the frozen design;
  * the mocked dry run has not passed.

Exit 0 = READY, non-zero = NOT READY.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-synthetic", action="store_true",
                    help="rehearsal only; NEVER for the confirmatory run")
    args = ap.parse_args()

    checks: dict[str, tuple[bool, str]] = {}

    # --- P1 corpus ---
    try:
        r = json.loads((REPO / "corpora/pipeline1/p1_corpus_report.json").read_text())
        ok = r["primary"]["n"] == 60 and r["stress"]["n"] == 20
        checks["p1_corpus"] = (ok, f"primary={r['primary']['n']} stress={r['stress']['n']} "
                                   f"sha={r['primary']['sha256'][:12]}")
    except Exception as e:  # noqa: BLE001
        checks["p1_corpus"] = (False, f"missing/unreadable: {e}")

    # --- P2 corpus: must be REAL ContractNLI ---
    try:
        r = json.loads((REPO / "corpora/pipeline2/p2_corpus_report.json").read_text())
        counts_ok = r["primary"]["n"] == 60 and r["stress"]["n"] == 20
        synthetic = r.get("is_synthetic_fixture", True)
        if synthetic and not args.allow_synthetic:
            checks["p2_corpus"] = (
                False,
                "SYNTHETIC FIXTURES — the real experiment requires genuine "
                "ContractNLI. Place the ToU-accepted download under "
                "data/raw/contractnli/ and rebuild with --source.")
        else:
            checks["p2_corpus"] = (
                counts_ok,
                f"{'SYNTHETIC (rehearsal)' if synthetic else 'real ContractNLI'} "
                f"primary={r['primary']['n']} stress={r['stress']['n']} "
                f"sha={r['primary']['sha256'][:12]}")
    except Exception as e:  # noqa: BLE001
        checks["p2_corpus"] = (False, f"missing/unreadable: {e}")

    # --- ContractNLI source validation ---
    vp = REPO / "corpora/pipeline2/contractnli_validation.json"
    if args.allow_synthetic and not vp.exists():
        checks["contractnli_validation"] = (True, "skipped (synthetic rehearsal)")
    else:
        try:
            v = json.loads(vp.read_text())
            checks["contractnli_validation"] = (
                v["status"] == "PASS",
                f"{v['status']} · {v['n_documents']} docs · src sha={v['sha256'][:12]}")
        except Exception as e:  # noqa: BLE001
            checks["contractnli_validation"] = (
                False, f"no validation report — run scripts/validate_contractnli.py ({e})")

    # --- protocol lock ---
    lock = REPO / "protocol/protocol_lock.json"
    if lock.exists():
        rc = subprocess.run([sys.executable, str(REPO / "protocol/freeze_protocol.py"),
                             "verify", "--lock", str(lock)],
                            capture_output=True, text=True)
        h = json.loads(lock.read_text()).get("protocol_hash", "")
        checks["protocol_lock"] = (rc.returncode == 0,
                                   f"{'verifies' if rc.returncode == 0 else 'DRIFT'} "
                                   f"hash={h[:16]}")
    else:
        checks["protocol_lock"] = (False, "not frozen")

    # --- git cleanliness ---
    dirty = _git("status", "--porcelain")
    checks["git_clean"] = (not dirty,
                           f"clean @ {_git('rev-parse', 'HEAD')[:12]}" if not dirty
                           else f"{len(dirty.splitlines())} uncommitted change(s)")

    # --- dry run ---
    try:
        d = json.loads((REPO / "results/dry_run_summary.json").read_text())
        checks["mock_dry_run"] = (d["status"] == "PASS",
                                  f"{d['status']} · {sum(b['results'] for b in d['blocks'])} records")
    except Exception as e:  # noqa: BLE001
        checks["mock_dry_run"] = (False, f"not run: {e}")

    ready = all(ok for ok, _ in checks.values())
    print(f"{'READY' if ready else 'NOT READY'}\n")
    for name, (ok, detail) in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
