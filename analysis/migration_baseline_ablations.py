#!/usr/bin/env python3
"""Ablation study: the variance-aware method against simpler alternatives.

Reads only existing confirmatory outputs. No model calls, no network.

Methods compared
----------------
A1 proposed            Delta = C_AB - W_A, off-diagonal W_A, task-aware CIs.
A2 deterministic       Assume the incumbent is a stable oracle (W_A = 1), so
                       Delta_det = C_AB - 1. This is conventional regression
                       logic, NOT a recommendation.
A3 panel/pooled        The pilot's symmetric panel statistic: one number per
                       property, averaging over all candidates.
A4 correctness-only    P2 gold accuracy change, ignoring behaviour.
A5 schema-only         Schema validity, against grounding / behaviour / gold.

The report states agreements as well as disagreements.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P2_TOL = 0.05          # frozen declared tolerance
DETERMINISTIC_W_A = 1.0


# ---------------- A2: deterministic-oracle ablation ----------------

def deterministic_delta(c_ab: float) -> float:
    """Delta under the assumption that the incumbent never varies."""
    return c_ab - DETERMINISTIC_W_A


def deterministic_gap(w_a: float) -> float:
    """Delta_det - Delta = (C_AB - 1) - (C_AB - W_A) = -(1 - W_A).

    Independent of C_AB: the deterministic assumption shifts every effect for a
    property by the same amount, namely the incumbent's own instability.
    """
    return -(1.0 - w_a)


def verdict(ci_lo: float, ci_hi: float, tau: float | None) -> str:
    if tau is None:
        return "no_declared_tolerance"
    if ci_hi < -tau or ci_lo > tau:
        return "rejected"
    if ci_lo >= -tau and ci_hi <= tau:
        return "demonstrated"
    return "inconclusive"


def qualitative_class(delta: float, tau: float) -> str:
    """Coarse reading of a point estimate against a tolerance."""
    if delta < -tau:
        return "worse_than_tolerance"
    if delta > tau:
        return "better_than_tolerance"
    return "within_tolerance"


# ---------------- A3: panel / pooled ----------------

def panel_pooled(rows: list[dict]) -> dict[str, dict]:
    """Pilot-style pooled statistic: average Delta per property over candidates.

    The pooled number is what the legacy panel formulation reports. It is
    reproduced here only to show what candidate-specific structure it hides.
    """
    by_prop: dict[str, list[dict]] = {}
    for r in rows:
        key = f'{r.get("pipeline","")}·{r["property"]}'.lstrip("·")
        by_prop.setdefault(key, []).append(r)
    out = {}
    for prop, rs in by_prop.items():
        # accepts either raw pairwise rows ("delta") or built rows
        deltas = [r.get("delta", r.get("A1_proposed_delta")) for r in rs]
        out[prop] = {
            "pooled_delta": st.mean(deltas),
            "candidate_min": min(deltas),
            "candidate_max": max(deltas),
            "candidate_spread": max(deltas) - min(deltas),
            "n_candidates": len(rs),
        }
    return out


# ---------------- loaders ----------------

def load_pairwise(path: Path) -> dict:
    return json.loads(path.read_text())


def load_extended(path: Path) -> dict:
    return json.loads(path.read_text())


def build_rows(pairwise: dict, extended: dict) -> list[dict]:
    """One row per (pipeline, property, candidate) with every ablation applied."""
    quad = {(q["property"], q["candidate"]): q for q in extended["quadrants"]}
    comp = {(c["model"], c["pipeline"], c["partition"]): c
            for c in extended["compliance"]}

    rows = []
    for pipeline in ("P1", "P2"):
        tau = P2_TOL if pipeline == "P2" else None
        for r in pairwise[pipeline]:
            w_a, c_ab, delta = r["W_A"], r["C_AB"], r["delta"]
            d_det = deterministic_delta(c_ab)
            gap = deterministic_gap(w_a)
            row = {
                "pipeline": pipeline, "property": r["property"],
                "candidate": r["candidate"],
                "W_A": round(w_a, 6), "C_AB": round(c_ab, 6),
                # A1 proposed
                "A1_proposed_delta": round(delta, 6),
                "A1_ci_lower": round(r["ci_lower"], 6),
                "A1_ci_upper": round(r["ci_upper"], 6),
                "A1_verdict": r["verdict"],
                # A2 deterministic oracle
                "A2_deterministic_delta": round(d_det, 6),
                "A2_minus_A1": round(d_det - delta, 6),
                "A2_theoretical_gap": round(gap, 6),
                # The frozen JSON stores W_A, C_AB and delta each rounded to
                # 6 dp, so (C_AB - W_A) and the stored delta can differ by up
                # to ~1e-6. The identity is exact in real arithmetic; the
                # tolerance here absorbs only that storage rounding.
                "A2_identity_holds": abs((d_det - delta) - gap) < 1e-5,
                "A2_identity_residual": abs((d_det - delta) - gap),
            }
            if tau is not None:
                q1 = qualitative_class(delta, tau)
                q2 = qualitative_class(d_det, tau)
                row["A1_qualitative"] = q1
                row["A2_qualitative"] = q2
                row["A2_changes_interpretation"] = q1 != q2
            else:
                row["A1_qualitative"] = row["A2_qualitative"] = "n/a_no_tolerance"
                row["A2_changes_interpretation"] = ""

            # A4 correctness-only (P2 has gold)
            key = (r["property"].replace("label_agreement", "label_accuracy")
                   .replace("cited_span_set_agreement", "span_f1"), r["candidate"])
            q = quad.get(key)
            if q:
                row["A4_incumbent_accuracy"] = round(q["incumbent_accuracy"], 6)
                row["A4_candidate_accuracy"] = round(q["candidate_accuracy"], 6)
                row["A4_accuracy_delta"] = round(q["accuracy_delta"], 6)
                row["A4_accuracy_ci_lower"] = round(q["accuracy_ci"][0], 6)
                row["A4_accuracy_ci_upper"] = round(q["accuracy_ci"][1], 6)
                row["A4_correctness_signal"] = (
                    "worse" if q["accuracy_ci"][1] < 0 else
                    "better" if q["accuracy_ci"][0] > 0 else "indeterminate")
                row["A4_quadrant"] = q["quadrant"]
            else:
                for k in ("A4_incumbent_accuracy", "A4_candidate_accuracy",
                          "A4_accuracy_delta", "A4_accuracy_ci_lower",
                          "A4_accuracy_ci_upper", "A4_correctness_signal",
                          "A4_quadrant"):
                    row[k] = ""

            # A5 schema-only
            c = comp.get((_model_key(r["candidate"]), pipeline, "primary"))
            if c:
                row["A5_schema_valid_rate"] = round(c["schema_valid_rate"], 6)
                row["A5_verbatim_grounding_rate"] = (
                    round(c["verbatim_grounding_rate"], 6)
                    if c.get("verbatim_grounding_rate") is not None else "")
            else:
                row["A5_schema_valid_rate"] = row["A5_verbatim_grounding_rate"] = ""
            rows.append(row)
    return rows


def _model_key(candidate: str) -> str:
    """Map the pairwise candidate label onto the compliance model id."""
    return candidate


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def summarise(rows: list[dict], pooled: dict) -> str:
    p2 = [r for r in rows if r["pipeline"] == "P2"]
    p1 = [r for r in rows if r["pipeline"] == "P1"]
    L = ["# Baseline / ablation study", "",
         "Comparison of the proposed variance-aware method against simpler",
         "migration-evaluation strategies, using only existing confirmatory",
         "outputs. No model calls.", "",
         "## A2 — deterministic-incumbent assumption", "",
         "Conventional regression logic treats the incumbent as a stable oracle",
         "(`W_A = 1`), giving `Delta_det = C_AB - 1`. The identity",
         "`Delta_det - Delta = -(1 - W_A)` holds for every cell "
         f"({sum(r['A2_identity_holds'] for r in rows)}/{len(rows)} verified).",
         "",
         "The shift depends only on the property, not the candidate: it is",
         "exactly the incumbent's own instability.", "",
         "| property | W_A | shift applied by the deterministic assumption |",
         "|---|---|---|"]
    seen = set()
    for r in sorted(rows, key=lambda r: r["W_A"]):
        if r["property"] in seen:
            continue
        seen.add(r["property"])
        L.append(f'| {r["pipeline"]}·{r["property"]} | {r["W_A"]:.4f} | '
                 f'{r["A2_theoretical_gap"]:+.4f} |')
    changed = [r for r in p2 if r["A2_changes_interpretation"] is True]
    L += ["", f"**Interpretation changes on {len(changed)}/{len(p2)} P2 cells**"
          " when the deterministic assumption is applied at the declared"
          " tolerance.", ""]
    if changed:
        L += ["| property | candidate | proposed | deterministic |", "|---|---|---|---|"]
        for r in changed:
            L.append(f'| {r["property"]} | {r["candidate"][:24]} | '
                     f'{r["A1_qualitative"]} | {r["A2_qualitative"]} |')
    L += ["", "## A3 — panel / pooled estimator", "",
          "The pilot's pooled statistic reports one number per property,",
          "averaging over candidates. The spread column shows what that hides.",
          "",
          "| property | pooled Delta | min candidate | max candidate | spread |",
          "|---|---|---|---|---|"]
    for prop, p in sorted(pooled.items(), key=lambda kv: -kv[1]["candidate_spread"]):
        L.append(f'| {prop} | {p["pooled_delta"]:+.4f} | {p["candidate_min"]:+.4f} '
                 f'| {p["candidate_max"]:+.4f} | {p["candidate_spread"]:.4f} |')
    worst = max(pooled.items(), key=lambda kv: kv[1]["candidate_spread"])
    L += ["", f"Largest concealment: **{worst[0]}**, where the pooled value "
          f'{worst[1]["pooled_delta"]:+.4f} spans candidates from '
          f'{worst[1]["candidate_min"]:+.4f} to {worst[1]["candidate_max"]:+.4f} '
          f'(spread {worst[1]["candidate_spread"]:.4f}).', ""]
    L += ["## A4 — correctness-only evaluation (P2)", "",
          "What an engineer would conclude from gold correctness alone.", "",
          "| property | candidate | behavioural Delta | accuracy Delta | "
          "correctness signal | quadrant |", "|---|---|---|---|---|---|"]
    for r in p2:
        if r["A4_correctness_signal"]:
            L.append(f'| {r["property"][:22]} | {r["candidate"][:22]} | '
                     f'{r["A1_proposed_delta"]:+.4f} | {r["A4_accuracy_delta"]:+.4f} '
                     f'| {r["A4_correctness_signal"]} | {r["A4_quadrant"][:28]} |')
    miss = [r for r in p2 if r["A4_correctness_signal"] == "indeterminate"
            and abs(r["A1_proposed_delta"]) > 0.10]
    L += ["", f"**Correctness alone misses substantial behavioural change in "
          f"{len(miss)} cell(s)**: the accuracy CI straddles zero while the "
          "behavioural effect exceeds 0.10 in magnitude.", ""]
    for r in miss:
        L.append(f'- {r["property"]} / {r["candidate"][:24]}: behavioural '
                 f'{r["A1_proposed_delta"]:+.4f}, accuracy '
                 f'{r["A4_accuracy_delta"]:+.4f} '
                 f'CI [{r["A4_accuracy_ci_lower"]:+.3f}, {r["A4_accuracy_ci_upper"]:+.3f}]')
    pen = [r for r in p2 if r["A4_correctness_signal"] in ("better", "indeterminate")
           and r["A1_verdict"] == "rejected"]
    L += ["", f"**Behavioural testing alone would penalise {len(pen)} cell(s)** "
          "that show no evidence of worse correctness.", ""]
    for r in pen:
        L.append(f'- {r["property"]} / {r["candidate"][:24]}: behaviourally '
                 f'rejected, accuracy {r["A4_accuracy_delta"]:+.4f} '
                 f'({r["A4_correctness_signal"]})')
    L += ["", "## A5 — schema-only evaluation", "",
          "| model | pipeline | schema valid | verbatim grounding |",
          "|---|---|---|---|"]
    seen2 = set()
    for r in rows:
        k = (r["candidate"], r["pipeline"])
        if k in seen2 or r["A5_schema_valid_rate"] == "":
            continue
        seen2.add(k)
        L.append(f'| {r["candidate"][:30]} | {r["pipeline"]} | '
                 f'{r["A5_schema_valid_rate"]:.4f} | '
                 f'{r["A5_verbatim_grounding_rate"] or "n/a"} |')
    invisible = [r for r in p2 if r["A5_schema_valid_rate"] == 1.0
                 and r["A1_verdict"] == "rejected"]
    L += ["", f"**{len(invisible)} of {len(p2)} P2 cells are rejected on "
          "behaviour while showing perfect (1.000) schema validity.** Schema "
          "validation alone would report no problem in any of them.", ""]
    return "\n".join(L) + "\n"


def plot(rows: list[dict], pooled: dict, out_pdf: Path, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    p2 = [r for r in rows if r["pipeline"] == "P2"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))

    # left: proposed vs deterministic on P2
    lbl = [f'{r["property"][:16]}\n{r["candidate"][:16]}' for r in p2]
    x = np.arange(len(p2))
    axes[0].bar(x - 0.2, [r["A1_proposed_delta"] for r in p2], 0.4,
                label="A1 proposed  $C_{AB}-W_A$", color="#2980b9")
    axes[0].bar(x + 0.2, [r["A2_deterministic_delta"] for r in p2], 0.4,
                label="A2 deterministic oracle  $C_{AB}-1$", color="#c0392b")
    axes[0].axhline(-P2_TOL, color="black", linestyle="--", linewidth=1)
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_xticks(x); axes[0].set_xticklabels(lbl, fontsize=6, rotation=90)
    axes[0].set_ylabel("migration effect")
    axes[0].set_title("A2: assuming a deterministic incumbent inflates every effect\n"
                      "by exactly $-(1-W_A)$", fontsize=10)
    axes[0].legend(fontsize=8); axes[0].grid(axis="y", alpha=0.3)

    # right: pooled vs candidate spread
    props = sorted(pooled, key=lambda p: -pooled[p]["candidate_spread"])
    y = np.arange(len(props))
    for i, p in enumerate(props):
        d = pooled[p]
        axes[1].plot([d["candidate_min"], d["candidate_max"]], [i, i],
                     color="#95a5a6", linewidth=3, solid_capstyle="round")
        axes[1].plot([d["pooled_delta"]], [i], marker="D", color="#c0392b",
                     markersize=6)
    axes[1].set_yticks(y); axes[1].set_yticklabels(props, fontsize=6)
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].set_xlabel("migration effect")
    axes[1].set_title("A3: pooled value (red) vs the candidate range it conceals",
                      fontsize=10)
    axes[1].grid(axis="x", alpha=0.3)

    fig.tight_layout()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams["pdf.compression"] = 0
    fig.savefig(out_pdf, metadata={"CreationDate": None})
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairwise", type=Path,
                    default=REPO / "results/analysis/pairwise_results.json")
    ap.add_argument("--extended", type=Path,
                    default=REPO / "results/analysis/extended_analysis.json")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/baseline_ablations.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/baseline_ablations_summary.md")
    ap.add_argument("--pdf", type=Path, default=REPO / "figures/baseline_ablations.pdf")
    ap.add_argument("--png", type=Path, default=REPO / "figures/baseline_ablations.png")
    args = ap.parse_args()

    pw = load_pairwise(args.pairwise)
    ex = load_extended(args.extended)
    rows = build_rows(pw, ex)
    pooled = panel_pooled(rows)
    write_csv(rows, args.csv)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(summarise(rows, pooled))
    plot(rows, pooled, args.pdf, args.png)
    print(json.dumps({
        "rows": len(rows),
        "identity_verified": sum(r["A2_identity_holds"] for r in rows),
        "p2_interpretation_changes": sum(
            1 for r in rows if r["A2_changes_interpretation"] is True),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
