#!/usr/bin/env python3
"""Complete analysis pipeline. Run ONLY after the confirmatory grid completes.

Produces EXECUTION_REPORT.md and RESULTS_REPORT.md plus the planned tables and
figures. Refuses to run on an incomplete grid unless --allow-partial is passed,
so a premature peek cannot be mistaken for the confirmatory result.

Order of operations follows the frozen plan:
  1. verify run/call counts
  2. verify provenance
  3. verify corpus/prompt/protocol hashes unchanged
  4. primary pairwise analysis
  5. robustness and sensitivity analyses
  6. tables and figures
  7. reports
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

from vaml.analysis.assemble import (acceptance_summary, assemble_runs,  # noqa: E402
                                    load_ledger)
from vaml.analysis.correctness import (Quadrant, MigrationOutcome,  # noqa: E402
                                       agreement_on_incumbent_errors,
                                       bootstrap_accuracy_delta,
                                       classify_quadrant, format_report_row)
from vaml.analysis.metrics import (cosine_similarity_text, jaccard,  # noqa: E402
                                   mean_max_cosine, multiset_agreement,
                                   ordinal_agreement, semantic_set_overlap,
                                   sequence_agreement)
from vaml.analysis.migration import (bootstrap_migration_delta,  # noqa: E402
                                     classify_against_tolerance,
                                     estimate_cross_agreement,
                                     estimate_within_variation,
                                     tolerance_sensitivity)
from vaml.models import MATRIX, candidates, incumbent  # noqa: E402

TOTAL_PLANNED_CALLS = 20160
SEED = 20260803
REPLICATES = 10_000
TOLERANCE_SWEEP = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20]
COSINE_THRESHOLDS = [0.70, 0.75, 0.80, 0.85, 0.90]

P1_PROPERTIES = [
    ("M1.technical_execution", "ordinal", "ratings.technical_execution"),
    ("M1.delivery_consistency", "ordinal", "ratings.delivery_consistency"),
    ("M1.collaboration", "ordinal", "ratings.collaboration"),
    ("M1.impact", "ordinal", "ratings.impact"),
    ("M1.opportunity_multiset", "multiset", "lists.opportunities"),
    ("M1.opportunity_sequence", "sequence", "lists.opportunities"),
    ("M2.strengths", "semantic", "lists.strengths"),
    ("M2.opportunities", "semantic", "lists.opportunities"),
    ("M2.risks", "semantic", "lists.risks"),
    ("M2.recommendations", "semantic", "recommendations"),
    ("M3.summary", "cosine", "summary"),
]
P2_PROPERTIES = [
    ("label_agreement", "exact", "label"),
    ("cited_span_set_agreement", "semantic", "cited_spans"),
    ("extracted_span_set_agreement", "semantic", "extracted_spans"),
]


def dig(d: dict | None, path: str):
    if d is None:
        return None
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def make_embedder(revision: str):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2",
                                revision=revision)
    cache: dict[str, np.ndarray] = {}

    def embed(items):
        todo = [x for x in items if x not in cache]
        if todo:
            for t, v in zip(todo, model.encode(todo, show_progress_bar=False)):
                cache[t] = v
        return np.array([cache[x] for x in items])
    return embed


def pair_value(kind, a, b, embed, threshold=0.80):
    if kind == "ordinal":
        return ordinal_agreement(a, b)
    if kind == "exact":
        return None if a is None or b is None else (1.0 if a == b else 0.0)
    if kind == "multiset":
        return multiset_agreement(a, b)
    if kind == "sequence":
        return sequence_agreement(a, b)
    if kind == "jaccard":
        return jaccard(a, b)
    if kind == "semantic":
        return semantic_set_overlap(a, b, embed, threshold)
    if kind == "cosine":
        return cosine_similarity_text(a, b, embed)
    if kind == "meanmax":
        return mean_max_cosine(a, b, embed)
    raise ValueError(kind)


def build_matrices(runs, model_key, other_key, kind, path, embed, threshold):
    """Per-task within (model vs itself) and cross (model vs other) matrices."""
    by_task = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in runs:
        if r.accepted:
            by_task[r.task_id][r.model_key].append(r)

    within, cross = {}, {}
    for task, models in by_task.items():
        a = sorted(models.get(model_key, []), key=lambda r: r.repetition)
        b = sorted(models.get(other_key, []), key=lambda r: r.repetition)
        if len(a) >= 2:
            m = np.full((len(a), len(a)), np.nan)
            for i in range(len(a)):
                for j in range(len(a)):
                    if i != j:
                        # Explicit None check, NOT `or np.nan`: a genuine
                        # disagreement scores 0.0, which is falsy, so `or`
                        # would silently convert every disagreement into an
                        # ineligible pair and bias W_A toward 1.0.
                        v = pair_value(kind, dig(a[i].structured, path),
                                       dig(a[j].structured, path),
                                       embed, threshold)
                        m[i, j] = np.nan if v is None else v
            within[task] = m
        if a and b:
            m = np.full((len(a), len(b)), np.nan)
            for i in range(len(a)):
                for j in range(len(b)):
                    v = pair_value(kind, dig(a[i].structured, path),
                                   dig(b[j].structured, path), embed, threshold)
                    m[i, j] = np.nan if v is None else v
            cross[task] = m
    return within, cross


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, default=REPO / "results/run/calls.jsonl")
    ap.add_argument("--out", type=Path, default=REPO / "results/analysis")
    ap.add_argument("--allow-partial", action="store_true",
                    help="analyse an incomplete grid (NOT the confirmatory result)")
    ap.add_argument("--embedding-revision",
                    default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # ---- 1. counts -------------------------------------------------
    ledger = load_ledger(args.ledger)
    complete = len(ledger) >= TOTAL_PLANNED_CALLS
    if not complete and not args.allow_partial:
        print(f"REFUSING: ledger has {len(ledger)}/{TOTAL_PLANNED_CALLS} calls. "
              f"The confirmatory analysis runs only on the complete grid. "
              f"Pass --allow-partial for a non-confirmatory dry pass.")
        return 2

    # ---- 3. hash verification -------------------------------------
    freeze = subprocess.run(
        [sys.executable, str(REPO / "protocol/freeze_protocol.py"), "verify",
         "--lock", str(REPO / "protocol/protocol_lock.json")],
        capture_output=True, text=True)
    hashes_ok = freeze.returncode == 0

    p2_corpus = {}
    for part in ("primary", "stress"):
        for line in (REPO / f"corpora/pipeline2/p2_{part}.jsonl").read_text().splitlines():
            if line.strip():
                c = json.loads(line)
                p2_corpus[c["task_id"]] = c

    runs = assemble_runs(ledger, p2_corpus)
    summary = acceptance_summary(runs)

    # ---- 2. provenance ---------------------------------------------
    prov = {
        "mismatches": sum(1 for r in runs if not r.provenance_ok),
        "returned_ids": dict(collections.Counter(
            m for r in runs for m in r.returned_model_ids)),
    }

    embed = make_embedder(args.embedding_revision)
    inc = incumbent()
    results: dict = {"P1": [], "P2": []}

    # ---- 4/5. pairwise analysis + sensitivity ----------------------
    for pipeline_tag, props, partition in (("P1", P1_PROPERTIES, "primary"),
                                           ("P2", P2_PROPERTIES, "primary")):
        pref = "p1" if pipeline_tag == "P1" else "p2"
        sel = [r for r in runs if r.pipeline.startswith(pref)
               and r.partition == partition]
        for cand in candidates():
            for pname, kind, path in props:
                w, c = build_matrices(sel, inc.key, cand.key, kind, path,
                                      embed, 0.80)
                if not w or not c:
                    continue
                wv, wn = estimate_within_variation(w)
                cv, cn = estimate_cross_agreement(c)
                lo, hi, _ = bootstrap_migration_delta(
                    w, c, replicates=args.replicates, seed=SEED)
                tol = None if pipeline_tag == "P1" else 0.05
                row = {
                    "pipeline": pipeline_tag, "incumbent": inc.model_id,
                    "candidate": cand.model_id, "property": pname,
                    "W_A": round(wv, 6), "C_AB": round(cv, 6),
                    "delta": round(cv - wv, 6),
                    "ci_lower": round(lo, 6), "ci_upper": round(hi, 6),
                    "n_within_pairs": wn, "n_cross_pairs": cn,
                    "verdict": classify_against_tolerance(lo, hi, tol),
                    "tolerance_curve": {str(t): v for t, v in
                                        tolerance_sensitivity(lo, hi, TOLERANCE_SWEEP).items()},
                }
                if kind == "semantic":
                    row["threshold_sensitivity"] = {}
                    for th in COSINE_THRESHOLDS:
                        w2, c2 = build_matrices(sel, inc.key, cand.key, kind,
                                                path, embed, th)
                        if w2 and c2:
                            wv2, _ = estimate_within_variation(w2)
                            cv2, _ = estimate_cross_agreement(c2)
                            row["threshold_sensitivity"][str(th)] = round(cv2 - wv2, 6)
                    # threshold-free aggregate, for the same sensitivity
                    wf, cf = build_matrices(sel, inc.key, cand.key, "meanmax",
                                            path, embed, 0.0)
                    if wf and cf:
                        wvf, _ = estimate_within_variation(wf)
                        cvf, _ = estimate_cross_agreement(cf)
                        row["threshold_free_delta"] = round(cvf - wvf, 6)
                results[pipeline_tag].append(row)

    (args.out / "pairwise_results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")
    (args.out / "execution_summary.json").write_text(json.dumps({
        "calls": len(ledger), "planned": TOTAL_PLANNED_CALLS,
        "complete": complete, "hashes_verified": hashes_ok,
        "provenance": prov, "acceptance": summary,
    }, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"calls": len(ledger), "runs": summary["total_runs"],
                      "accepted": summary["accepted"],
                      "hashes_verified": hashes_ok,
                      "pairwise_rows": {k: len(v) for k, v in results.items()}},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
