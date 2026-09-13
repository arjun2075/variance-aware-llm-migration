#!/usr/bin/env python3
"""Tolerance non-vacuity diagnostic.

A migration verdict compares Delta = C_AB - W_A against a symmetric tolerance
tau. Because every agreement score is bounded in [0, 1], Delta is *not* free to
range over [-1, 1]: it is bounded by the incumbent's own self-agreement.

    0 <= C_AB <= 1  and  Delta = C_AB - W_A
    =>  -W_A <= Delta <= 1 - W_A

The lower bound is the operative one. Delta = -W_A is attained exactly when
C_AB = 0, i.e. the candidate and incumbent agree on *nothing*. Rearranging the
acceptance condition Delta >= -tau gives the implied floor on cross-model
agreement:

    C_AB >= max(0, W_A - tau)

When tau >= W_A that floor collapses to 0, so even total disagreement satisfies
the tolerance. The diagnostic ratio

    vacuity_ratio = tau / W_A            (W_A > 0)

therefore separates two regimes:

  * ratio  < 1  -- C_AB = 0 lies OUTSIDE the tolerance region; the tolerance can
                   in principle exclude complete disagreement.
  * ratio >= 1  -- C_AB = 0 gives Delta = -W_A >= -tau, which the tolerance
                   ACCEPTS. The test cannot exclude complete disagreement and is
                   vacuous on the negative side for that property.

This is a DIAGNOSTIC, not an estimator. It does not replace Delta as the paper's
primary quantity; it reports whether a chosen tau is informative relative to the
incumbent variability of each property.

No network, no model calls, fully deterministic.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PILOT_TAU = 0.10


def delta_bounds(w_a: float) -> tuple[float, float]:
    """Feasible range of Delta given the incumbent self-agreement W_A."""
    _validate(w_a, "W_A")
    return (-w_a, 1.0 - w_a)


def min_acceptable_cross_agreement(w_a: float, tau: float) -> float:
    """Smallest C_AB satisfying Delta >= -tau, clipped at the [0,1] floor."""
    _validate(w_a, "W_A")
    _validate_tau(tau)
    return max(0.0, w_a - tau)


def vacuity_ratio(w_a: float, tau: float) -> float:
    """tau / W_A. Infinite when W_A == 0 (any tau accepts everything)."""
    _validate(w_a, "W_A")
    _validate_tau(tau)
    if w_a == 0.0:
        return math.inf
    return tau / w_a


def is_vacuous(w_a: float, tau: float) -> bool:
    """True when the tolerance cannot exclude C_AB = 0.

    Equivalent to tau >= W_A, including the W_A = 0 case where every tau is
    vacuous. Expressed directly rather than via the ratio so the W_A = 0 case
    does not depend on inf comparison semantics.
    """
    _validate(w_a, "W_A")
    _validate_tau(tau)
    return tau >= w_a


def _validate(v: float, name: str) -> None:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise TypeError(f"{name} must be numeric, got {type(v).__name__}")
    if math.isnan(v):
        raise ValueError(f"{name} must not be NaN")
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"{name} must lie in [0,1], got {v}")


def _validate_tau(tau: float) -> None:
    if not isinstance(tau, (int, float)) or isinstance(tau, bool):
        raise TypeError(f"tau must be numeric, got {type(tau).__name__}")
    if math.isnan(tau):
        raise ValueError("tau must not be NaN")
    if tau < 0.0:
        raise ValueError(f"tau must be non-negative, got {tau}")


def load_frozen_w_a(path: Path) -> list[dict]:
    """Read the frozen per-property W_A values. Never modifies the source."""
    data = json.loads(path.read_text())
    seen: dict[tuple[str, str], float] = {}
    for pipeline in ("P1", "P2"):
        for row in data.get(pipeline, []):
            seen.setdefault((pipeline, row["property"]), float(row["W_A"]))
    return [{"pipeline": p, "property": prop, "W_A": w}
            for (p, prop), w in sorted(seen.items())]


def build_rows(records: list[dict], tau: float = PILOT_TAU) -> list[dict]:
    out = []
    for rec in records:
        w = rec["W_A"]
        lo, hi = delta_bounds(w)
        ratio = vacuity_ratio(w, tau)
        out.append({
            "pipeline": rec["pipeline"],
            "property": rec["property"],
            "W_A": round(w, 6),
            "tau": tau,
            "delta_lower_bound": round(lo, 6),
            "delta_upper_bound": round(hi, 6),
            "min_acceptable_C_AB": round(min_acceptable_cross_agreement(w, tau), 6),
            "vacuity_ratio": "inf" if math.isinf(ratio) else round(ratio, 6),
            "tolerance_vacuous": is_vacuous(w, tau),
        })
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def plot(rows: list[dict], out_pdf: Path, out_png: Path, tau: float = PILOT_TAU) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(rows, key=lambda r: r["W_A"])
    labels = [f'{r["pipeline"]}·{r["property"]}' for r in ordered]
    vals = [r["W_A"] for r in ordered]
    vacuous = [r["tolerance_vacuous"] for r in ordered]

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#c0392b" if v else "#2980b9" for v in vacuous]
    ax.barh(range(len(vals)), vals, color=colors)
    ax.axvline(tau, color="black", linestyle="--", linewidth=1.5,
               label=f"pilot tolerance τ = {tau:.2f}")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("incumbent self-agreement  $W_A$")
    ax.set_xlim(0, 1)
    ax.set_title("Tolerance non-vacuity: properties where τ ≥ $W_A$\n"
                 "(red — τ cannot exclude $C_{AB}=0$)", fontsize=11)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#c0392b", label=r"vacuous: $\tau \geq W_A$"),
        Patch(facecolor="#2980b9", label=r"informative: $\tau < W_A$"),
        plt.Line2D([0], [0], color="black", linestyle="--",
                   label=f"τ = {tau:.2f}")],
        loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    # deterministic PDF: suppress the embedded creation timestamp
    matplotlib.rcParams["pdf.compression"] = 0
    fig.savefig(out_pdf, metadata={"CreationDate": None})
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairwise", type=Path,
                    default=REPO / "results/analysis/pairwise_results.json")
    ap.add_argument("--tau", type=float, default=PILOT_TAU)
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/tolerance_nonvacuity.csv")
    ap.add_argument("--pdf", type=Path, default=REPO / "figures/tolerance_nonvacuity.pdf")
    ap.add_argument("--png", type=Path, default=REPO / "figures/tolerance_nonvacuity.png")
    args = ap.parse_args()

    rows = build_rows(load_frozen_w_a(args.pairwise), args.tau)
    write_csv(rows, args.csv)
    plot(rows, args.pdf, args.png, args.tau)
    vac = [r for r in rows if r["tolerance_vacuous"]]
    print(json.dumps({
        "properties": len(rows),
        "tau": args.tau,
        "vacuous_count": len(vac),
        "vacuous_properties": [f'{r["pipeline"]}.{r["property"]}' for r in vac],
        "csv": str(args.csv), "pdf": str(args.pdf), "png": str(args.png),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
