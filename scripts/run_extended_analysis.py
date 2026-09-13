#!/usr/bin/env python3
"""Extended frozen analyses: quadrants, stress sets, LOTO, order, compliance.

Uses the frozen metric definitions, tolerances, thresholds and exclusion rules
unchanged. Adds no new estimand and no exploratory analysis.
"""
from __future__ import annotations

import argparse, collections, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
from run_analysis import (P1_PROPERTIES, P2_PROPERTIES, build_matrices, dig,  # noqa: E402
                          make_embedder)
from vaml.analysis.assemble import assemble_runs, load_ledger  # noqa: E402
from vaml.analysis.correctness import (Quadrant, agreement_on_incumbent_errors,  # noqa: E402
                                       bootstrap_accuracy_delta, classify_quadrant)
from vaml.analysis.metrics import jaccard  # noqa: E402
from vaml.analysis.migration import (bootstrap_migration_delta,  # noqa: E402
                                     classify_against_tolerance,
                                     estimate_cross_agreement,
                                     estimate_within_variation)
from vaml.models import MATRIX, candidates, incumbent  # noqa: E402

SEED = 20260803
REPS = 10_000
P2_LABEL_TOL = 0.05          # frozen
COSINE = 0.80                # frozen


def p2_corpus() -> dict:
    out = {}
    for part in ("primary", "stress"):
        for line in (REPO / f"corpora/pipeline2/p2_{part}.jsonl").read_text().splitlines():
            if line.strip():
                c = json.loads(line); out[c["task_id"]] = c
    return out


def label_correct(run, corpus) -> bool | None:
    lab = (run.structured or {}).get("label")
    gold = corpus.get(run.task_id, {}).get("gold_label")
    return None if lab is None or gold is None else lab == gold


def span_f1(run, corpus) -> float | None:
    pred = set(s.strip().lower() for s in (run.structured or {}).get("cited_spans", []) if s.strip())
    gold = set(s.strip().lower() for s in corpus.get(run.task_id, {}).get("gold_spans", []) if s.strip())
    if not gold and not pred:
        return 1.0
    if not gold or not pred:
        return 0.0
    inter = len(pred & gold)
    p = inter / len(pred); r = inter / len(gold)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "results/analysis")
    ap.add_argument("--replicates", type=int, default=REPS)
    ap.add_argument("--embedding-revision", default="e8c3b32edf5434bc2275fc9bab85f82640a19130")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    corpus = p2_corpus()
    ledger = load_ledger(REPO / "results/run/calls.jsonl")
    runs = assemble_runs(ledger, corpus)
    embed = make_embedder(args.embedding_revision)
    inc = incumbent()
    out: dict = {}

    # ---------- 1. quadrants (P2 primary) ----------
    sel = [r for r in runs if r.pipeline.startswith("p2") and r.partition == "primary" and r.accepted]
    by = collections.defaultdict(list)
    for r in sel:
        by[(r.task_id, r.model_key)].append(r)
    tasks = sorted({t for t, _ in by})

    def acc_vectors(model_key, fn):
        ts, vals = [], []
        for t in tasks:
            for r in by.get((t, model_key), []):
                v = fn(r, corpus)
                if v is not None:
                    ts.append(t); vals.append(float(v))
        return ts, vals

    quad_rows = []
    for prop, fn in (("label_accuracy", label_correct), ("span_f1", span_f1)):
        it, iv = acc_vectors(inc.key, fn)
        for cand in candidates():
            ct, cv = acc_vectors(cand.key, fn)
            # align on shared tasks, task-mean per side (unequal reps)
            im = collections.defaultdict(list); cm = collections.defaultdict(list)
            for t, v in zip(it, iv): im[t].append(v)
            for t, v in zip(ct, cv): cm[t].append(v)
            shared = sorted(set(im) & set(cm))
            iacc = [float(np.mean(im[t])) for t in shared]
            cacc = [float(np.mean(cm[t])) for t in shared]
            point, lo, hi = bootstrap_accuracy_delta(iacc, cacc, shared,
                                                     replicates=args.replicates, seed=SEED)
            # behavioural delta for the matching property
            bprop = "label_agreement" if prop == "label_accuracy" else "cited_span_set_agreement"
            kind, path = next((k, p) for n, k, p in P2_PROPERTIES if n == bprop)
            w, c = build_matrices(sel, inc.key, cand.key, kind, path, embed, COSINE)
            wv, _ = estimate_within_variation(w); cv2, _ = estimate_cross_agreement(c)
            blo, bhi, _ = bootstrap_migration_delta(w, c, replicates=args.replicates, seed=SEED)
            bdelta = cv2 - wv
            preserved = classify_against_tolerance(blo, bhi, P2_LABEL_TOL) == "demonstrated"
            inc_acc = float(np.mean(iacc))
            q = classify_quadrant(preserved, point, (lo, hi), inc_acc)
            # agreement restricted to items the incumbent got wrong
            beh_by_task = {t: float(np.nanmean(c[t])) if t in c else np.nan for t in shared}
            aoe, n_err = agreement_on_incumbent_errors(
                [a >= 0.999 for a in iacc], [beh_by_task[t] for t in shared])
            quad_rows.append({
                "property": prop, "candidate": cand.model_id,
                "behavioural_delta": round(bdelta, 6),
                "behavioural_ci": [round(blo, 6), round(bhi, 6)],
                "behaviour_preserved": preserved,
                "incumbent_accuracy": round(inc_acc, 6),
                "candidate_accuracy": round(float(np.mean(cacc)), 6),
                "accuracy_delta": round(point, 6),
                "accuracy_ci": [round(lo, 6), round(hi, 6)],
                "quadrant": q.value,
                "is_success": q in (Quadrant.C_PRESERVED_CORRECT, Quadrant.A_CHANGED_IMPROVED),
                "agreement_on_incumbent_errors": None if aoe is None else round(aoe, 6),
                "n_incumbent_error_tasks": n_err,
            })
    out["quadrants"] = quad_rows

    # ---------- 2. stress sets ----------
    stress = []
    for tag, props, pref in (("P1", P1_PROPERTIES, "p1"), ("P2", P2_PROPERTIES, "p2")):
        s = [r for r in runs if r.pipeline.startswith(pref) and r.partition == "stress" and r.accepted]
        for cand in candidates():
            for pname, kind, path in props:
                w, c = build_matrices(s, inc.key, cand.key, kind, path, embed, COSINE)
                if not w or not c:
                    continue
                wv, wn = estimate_within_variation(w); cv, cn = estimate_cross_agreement(c)
                lo, hi, _ = bootstrap_migration_delta(w, c, replicates=args.replicates, seed=SEED)
                tol = None if tag == "P1" else P2_LABEL_TOL
                stress.append({"pipeline": tag, "candidate": cand.model_id, "property": pname,
                               "W_A": round(wv, 6), "C_AB": round(cv, 6),
                               "delta": round(cv - wv, 6),
                               "ci_lower": round(lo, 6), "ci_upper": round(hi, 6),
                               "n_within": wn, "n_cross": cn,
                               "verdict": classify_against_tolerance(lo, hi, tol)})
    out["stress"] = stress

    # ---------- 3. leave-one-task-out (P2 primary) ----------
    loto = []
    for cand in candidates():
        for pname, kind, path in P2_PROPERTIES:
            w, c = build_matrices(sel, inc.key, cand.key, kind, path, embed, COSINE)
            base_w, _ = estimate_within_variation(w); base_c, _ = estimate_cross_agreement(c)
            base = base_c - base_w
            lo0, hi0, _ = bootstrap_migration_delta(w, c, replicates=2000, seed=SEED)
            base_v = classify_against_tolerance(lo0, hi0, P2_LABEL_TOL)
            deltas, flips = [], []
            for t in sorted(w):
                w2 = {k: v for k, v in w.items() if k != t}
                c2 = {k: v for k, v in c.items() if k != t}
                if not w2 or not c2:
                    continue
                ww, _ = estimate_within_variation(w2); cc, _ = estimate_cross_agreement(c2)
                d = cc - ww; deltas.append(d)
                l2, h2, _ = bootstrap_migration_delta(w2, c2, replicates=2000, seed=SEED)
                if classify_against_tolerance(l2, h2, P2_LABEL_TOL) != base_v:
                    flips.append(t)
            loto.append({"pipeline": "P2", "candidate": cand.model_id, "property": pname,
                         "base_delta": round(base, 6), "base_verdict": base_v,
                         "loto_min": round(min(deltas), 6), "loto_max": round(max(deltas), 6),
                         "max_abs_shift": round(max(abs(d - base) for d in deltas), 6),
                         "verdict_flips": flips, "n_flips": len(flips), "n_tasks": len(deltas)})
    out["loto"] = loto

    # ---------- 4. execution-order diagnostic ----------
    order = []
    for tag, pref in (("P1", "p1"), ("P2", "p2")):
        s = [r for r in runs if r.pipeline.startswith(pref) and r.partition == "primary" and r.accepted]
        idx = {}
        for rec in ledger:
            if rec.get("execution_order_index") is not None:
                idx[rec["rid"].rsplit("|", 1)[0]] = rec["execution_order_index"]
        for m in MATRIX:
            xs, ys = [], []
            for r in s:
                if r.model_key != m.key:
                    continue
                key = f"{r.pipeline}|{r.partition}|{r.task_id}|{r.model_key}|r{r.repetition}"
                if key in idx and r.schema_valid is not None:
                    xs.append(idx[key]); ys.append(1.0 if r.schema_valid else 0.0)
            if len(xs) > 30 and len(set(ys)) > 1:
                r_pear = float(np.corrcoef(xs, ys)[0, 1])
            else:
                r_pear = float("nan")
            # latency drift
            lx, ly = [], []
            for rec in ledger:
                if rec["error"] or not rec.get("latency_ms"):
                    continue
                if rec.get("returned_model_id") != (
                        json.loads((REPO / "protocol/canonical_model_map.json").read_text())
                        ["mapping"].get(m.model_id)):
                    continue
                if rec.get("execution_order_index") is None:
                    continue
                lx.append(rec["execution_order_index"]); ly.append(rec["latency_ms"])
            lat_r = float(np.corrcoef(lx, ly)[0, 1]) if len(lx) > 30 else float("nan")
            order.append({"pipeline": tag, "model": m.model_id,
                          "schema_valid_vs_order_r": None if np.isnan(r_pear) else round(r_pear, 4),
                          "latency_vs_order_r": None if np.isnan(lat_r) else round(lat_r, 4),
                          "n": len(xs)})
    out["order"] = order

    # ---------- 5. compliance ----------
    comp = []
    for tag, pref in (("P1", "p1"), ("P2", "p2")):
        for part in ("primary", "stress"):
            s = [r for r in runs if r.pipeline.startswith(pref) and r.partition == part and r.accepted]
            for m in MATRIX:
                rs = [r for r in s if r.model_key == m.key]
                if not rs:
                    continue
                row = {"pipeline": tag, "partition": part, "model": m.model_id,
                       "n_runs": len(rs),
                       "schema_valid_rate": round(sum(r.schema_valid for r in rs) / len(rs), 6),
                       "parse_failure_rate": round(sum(1 for r in rs if r.parse_failures) / len(rs), 6)}
                if pref == "p2":
                    gr = [r.structured.get("grounding_rate") for r in rs
                          if r.structured and r.structured.get("grounding_rate") is not None]
                    row["verbatim_grounding_rate"] = round(float(np.mean(gr)), 6) if gr else None
                    row["label_in_declared_set_rate"] = round(
                        sum(1 for r in rs if (r.structured or {}).get("label")) / len(rs), 6)
                comp.append(row)
    out["compliance"] = comp

    (args.out / "extended_analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: len(v) for k, v in out.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
