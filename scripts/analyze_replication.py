#!/usr/bin/env python3
"""Compare the direct-provider replication against the managed execution path confirmatory run.

Restricts BOTH sides to the same frozen 10+10 task subset and the same two
conditions, so the only difference is the serving path. Metric definitions,
tolerance and semantic threshold are frozen and unchanged.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))

from run_analysis import (P1_PROPERTIES, P2_PROPERTIES, build_matrices,  # noqa: E402
                          make_embedder)
from vaml.analysis.assemble import assemble_runs, load_ledger  # noqa: E402
from vaml.analysis.migration import (bootstrap_migration_delta,  # noqa: E402
                                     classify_against_tolerance,
                                     estimate_cross_agreement,
                                     estimate_within_variation)

SEED = 20260803
REPS = 10_000
COSINE = 0.80
P2_TOL = 0.05
INC, CAND = "incumbent_gpt4o", "candidate_gpt54"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "results/analysis/replication_comparison.json")
    ap.add_argument("--replicates", type=int, default=REPS)
    ap.add_argument("--embedding-revision", default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    args = ap.parse_args()

    subset = json.loads((REPO / "protocol/replication_subset.json").read_text())
    p1_ids, p2_ids = set(subset["P1_task_ids"]), set(subset["P2_task_ids"])

    corpus = {}
    for part in ("primary", "stress"):
        for line in (REPO / f"corpora/pipeline2/p2_{part}.jsonl").read_text().splitlines():
            if line.strip():
                c = json.loads(line); corpus[c["task_id"]] = c

    gw = assemble_runs(load_ledger(REPO / "results/run/calls.jsonl"), corpus)
    rp = assemble_runs(load_ledger(REPO / "results/replication/calls.jsonl"), corpus)
    embed = make_embedder(args.embedding_revision)

    rows = []
    for tag, props, pref, ids in (("P1", P1_PROPERTIES, "p1", p1_ids),
                                  ("P2", P2_PROPERTIES, "p2", p2_ids)):
        g = [r for r in gw if r.pipeline.startswith(pref) and r.partition == "primary"
             and r.accepted and r.task_id in ids and r.model_key in (INC, CAND)]
        d = [r for r in rp if r.pipeline.startswith(pref) and r.accepted
             and r.task_id in ids and r.model_key in (INC, CAND)]
        for pname, kind, path in props:
            out = {"pipeline": tag, "property": pname,
                   "incumbent": "gpt-4o-2024-11-20", "candidate": "gpt-5.4-2026-03-05"}
            for label, runs in (("managed execution path", g), ("direct", d)):
                w, c = build_matrices(runs, INC, CAND, kind, path, embed, COSINE)
                if not w or not c:
                    out[label] = None; continue
                wv, wn = estimate_within_variation(w); cv, cn = estimate_cross_agreement(c)
                lo, hi, _ = bootstrap_migration_delta(w, c, replicates=args.replicates, seed=SEED)
                tol = None if tag == "P1" else P2_TOL
                out[label] = {"W_A": round(wv, 6), "C_AB": round(cv, 6),
                              "delta": round(cv - wv, 6),
                              "ci": [round(lo, 6), round(hi, 6)],
                              "n_within": wn, "n_cross": cn,
                              "verdict": classify_against_tolerance(lo, hi, tol)}
            if out.get("managed execution path") and out.get("direct"):
                gd, dd = out["managed execution path"]["delta"], out["direct"]["delta"]
                glo, ghi = out["managed execution path"]["ci"]; dlo, dhi = out["direct"]["ci"]
                out["delta_difference"] = round(dd - gd, 6)
                # bool() casts: numpy bools are not JSON-serialisable
                out["same_sign"] = bool((gd < 0) == (dd < 0))
                out["cis_overlap"] = bool(not (ghi < dlo or dhi < glo))
                out["same_verdict"] = bool(
                    out["managed execution path"]["verdict"] == out["direct"]["verdict"])
            rows.append(out)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    ev = [r for r in rows if r.get("managed execution path") and r.get("direct")]
    print(json.dumps({"rows": len(rows), "evaluable": len(ev),
                      "same_sign": sum(1 for r in ev if r["same_sign"]),
                      "cis_overlap": sum(1 for r in ev if r["cis_overlap"]),
                      "same_verdict": sum(1 for r in ev if r["same_verdict"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
