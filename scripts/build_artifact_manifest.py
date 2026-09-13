#!/usr/bin/env python3
"""Generate ARTIFACT_MANIFEST.json / .md for the reviewer artifact.

Records hashes, seeds, environment and expected outputs so a reviewer can
verify the artifact has not drifted. Reads only; changes no scientific result.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCIENTIFIC_FREEZE_COMMIT = "3652060"
SEED = 20260803


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hashes(paths) -> dict:
    out = {}
    for rel in paths:
        p = REPO / rel
        if p.exists():
            out[rel] = sha256(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-result", default="451 passed, 1 skipped")
    ap.add_argument("--packaging-commit", default=None,
                    help="commit this manifest documents; defaults to HEAD. "
                         "Pin it to avoid a manifest/commit circular update.")
    ap.add_argument("--json-out", type=Path, default=REPO / "ARTIFACT_MANIFEST.json")
    ap.add_argument("--md-out", type=Path, default=REPO / "ARTIFACT_MANIFEST.md")
    args = ap.parse_args()

    head = args.packaging_commit or subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True, text=True).stdout.strip()

    m = {
        "artifact": "variance-aware-llm-migration",
        "title": ("Variance-Aware Regression Testing for Model Migration in "
                  "Compound LLM Pipelines"),
        "venue": "IEEE Transactions on Software Engineering (submission)",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "packaging_commit": head,
        "environment": {
            "python_version": "3.11.14",
            "python_running_manifest": platform.python_version(),
            "platform": platform.platform(),
            "dependency_lock": "requirements.lock.txt",
            "dependency_lock_sha256": sha256(REPO / "requirements.lock.txt"),
        },
        "seeds": {
            "global_random_seed": SEED,
            "bootstrap_seed": SEED,
            "corpus_build_seed": SEED,
            "execution_order_seed": SEED,
            "replication_subset_seed": SEED + 9001,
        },
        "embedding_model": {
            "name": "sentence-transformers/all-mpnet-base-v2",
            "revision": "e8c3b32edf5434bc2275fc9bab85f82640a19130",
            "cosine_match_threshold": 0.80,
        },
        "design": {
            "pipelines": 2, "primary_tasks_per_pipeline": 60,
            "stress_tasks_per_pipeline": 20,
            "incumbent_repetitions": 8, "candidate_repetitions": 5,
            "candidates": 4, "stages_per_run": 4,
            "total_runs": 5040, "total_calls": 20160,
            "bootstrap_replicates": 10000,
            "p2_declared_tolerance": 0.05,
            "p1_declared_tolerance": None,
        },
        "corpus_hashes": hashes([
            "corpora/pipeline1/p1_primary.jsonl",
            "corpora/pipeline1/p1_stress.jsonl",
            "corpora/pipeline2/p2_primary.jsonl",
            "corpora/pipeline2/p2_stress.jsonl",
        ]),
        "prompt_hashes": hashes([
            f"prompts/pipeline1/{n}" for n in
            ("stage1_pr_signal.md", "stage2_review_signal.md",
             "stage3_synthesis.md", "stage4_deepen.md")
        ] + [
            f"prompts/pipeline2/{n}" for n in
            ("stage1_extract_evidence.md", "stage2_assess_evidence.md",
             "stage3_classify.md", "stage4_verify.md")
        ]),
        "protocol_hashes": hashes([
            "protocol/protocol_lock.json", "protocol/protocol_spec.json",
            "protocol/PROTOCOL.md", "protocol/canonical_model_map.json",
            "protocol/replication_subset.json",
        ]),
        "confirmatory_ledger": hashes(["results/run/calls.jsonl"]),
        "primary_analysis_hashes": hashes([
            "results/analysis/pairwise_results.json",
            "results/analysis/extended_analysis.json",
            "results/analysis/execution_summary.json",
            "results/analysis/replication_comparison.json",
        ]),
        "strengthening_hashes": hashes([
            f"results/strengthening/{n}" for n in (
                "tolerance_nonvacuity.csv", "bootstrap_coverage.csv",
                "p2_tolerance_transition_points.csv", "baseline_ablations.csv",
                "single_run_oracle_instability.csv", "evaluation_budget.csv",
                "bootstrap_resolution_sensitivity.csv",
                "simultaneous_inference.csv", "invalid_output_sensitivity.csv",
                "contractnli_subset_representativeness.csv")
        ]),
        "test_result": args.test_result,
        "expected_figures": sorted(
            p.name for p in (REPO / "figures").glob("*") if p.is_file()),
        "expected_tables": sorted(
            p.name for p in (REPO / "results/strengthening").glob("*.csv")),
        "reports": ["EXECUTION_REPORT.md", "RESULTS_REPORT.md",
                    "REPLICATION_REPORT.md"],
        "non_authoritative_directories": {
            "results/aborted_qc_run/": (
                "Quarantined pre-confirmatory QC data: 82 calls made at the "
                "pre-Amendment-001 output ceiling. NEVER used in any reported "
                "result. Retained for audit; its ledger hash is test-verified."),
            "results/analysis_BUGGY_DISCARDED/": (
                "Output of a superseded analysis pass containing a corrected "
                "defect. NEVER authoritative. Retained only for auditability."),
        },
        "authoritative_analysis": (
            "results/analysis/ and results/strengthening/ at scientific freeze "
            "commit " + SCIENTIFIC_FREEZE_COMMIT),
        "excluded_from_release": {
            "data/raw/contractnli/*.json": (
                "ContractNLI source files. CC BY 4.0 but distributed behind a "
                "click-through Terms of Use; not redistributed. Expected "
                "train.json SHA-256 "
                "dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5"),
            "data/raw/contractnli/{LICENSE,TERMS}": (
                "Upstream dataset license files, intentionally not re-published."),
            ".git/": "version-control history",
            "__pycache__/, *.pyc": "interpreter caches",
            ".venv/, venv/": "virtual environments",
            "*.log, results/run/*.pre_*": "logs and ledger backups",
            ".replication.env, .env, vaml.env": "credential files, never committed",
        },
        "post_freeze_source_changes": {
            "commit": "e30c78e",
            "files": ["src/vaml/adapters/shim.py", "scripts/run_experiment.py"],
            "reason": ("Documented mid-run auth-recovery fix after a host "
                       "restart left the execution transport helper with stale credentials. "
                       "Recorded in EXECUTION_REPORT.md section 7. Changes "
                       "execution infrastructure only; no experimental "
                       "condition, corpus, prompt or estimand was altered."),
        },
    }

    args.json_out.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")

    L = ["# Artifact manifest", "",
         f"**Scientific freeze commit:** `{m['scientific_freeze_commit']}`  ",
         f"**Packaging commit:** `{m['packaging_commit']}`  ",
         f"**Generated:** {m['generated_at']}  ",
         f"**Tests:** {m['test_result']}", "",
         "Machine-readable form: `ARTIFACT_MANIFEST.json`.", "",
         "## Environment", "",
         f"- Python **{m['environment']['python_version']}**",
         f"- lock `requirements.lock.txt` "
         f"sha256 `{m['environment']['dependency_lock_sha256'][:32]}...`",
         f"- embedding `{m['embedding_model']['name']}` @ "
         f"`{m['embedding_model']['revision'][:16]}...`, cosine "
         f"{m['embedding_model']['cosine_match_threshold']}", "",
         "## Seeds", ""]
    for k, v in m["seeds"].items():
        L.append(f"- `{k}` = {v}")
    L += ["", "## Design", "",
          "| parameter | value |", "|---|---|"]
    for k, v in m["design"].items():
        L.append(f"| {k} | {v} |")
    for title, key in (("Corpus hashes", "corpus_hashes"),
                       ("Prompt hashes", "prompt_hashes"),
                       ("Protocol hashes", "protocol_hashes"),
                       ("Confirmatory ledger", "confirmatory_ledger"),
                       ("Primary analysis outputs", "primary_analysis_hashes"),
                       ("Strengthening outputs", "strengthening_hashes")):
        L += ["", f"## {title}", "", "| file | sha256 |", "|---|---|"]
        for f, h in sorted(m[key].items()):
            L.append(f"| `{f}` | `{h}` |")
    L += ["", "## Non-authoritative directories", ""]
    for d, why in m["non_authoritative_directories"].items():
        L.append(f"- **`{d}`** — {why}")
    L += ["", f"The authoritative analysis is {m['authoritative_analysis']}.", "",
          "## Excluded from the release archive", ""]
    for f, why in m["excluded_from_release"].items():
        L.append(f"- `{f}` — {why}")
    L += ["", "## Post-freeze source changes", "",
          f"Commit `{m['post_freeze_source_changes']['commit']}` touching "
          + ", ".join(f"`{f}`" for f in m["post_freeze_source_changes"]["files"])
          + ".", "", m["post_freeze_source_changes"]["reason"], "",
          "## Expected generated outputs", "",
          f"**Figures ({len(m['expected_figures'])}):** "
          + ", ".join(f"`{f}`" for f in m["expected_figures"]), "",
          f"**Tables ({len(m['expected_tables'])}):** "
          + ", ".join(f"`{f}`" for f in m["expected_tables"]), ""]
    args.md_out.write_text("\n".join(L) + "\n")
    print(json.dumps({"json": str(args.json_out), "md": str(args.md_out),
                      "corpus_files": len(m["corpus_hashes"]),
                      "prompt_files": len(m["prompt_hashes"]),
                      "figures": len(m["expected_figures"]),
                      "tables": len(m["expected_tables"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
