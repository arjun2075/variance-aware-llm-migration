#!/usr/bin/env python3
"""Monte Carlo study of estimator bias and interval coverage for Delta.

Demonstrates two distinct failure modes in migration testing:

  1. DIAGONAL CONTAMINATION. Including incumbent self-pairs in W_A adds
     comparisons that score 1.0 by construction. This biases W_A UP and
     therefore Delta = C_AB - W_A DOWN. It is a point-estimate bias and is
     present regardless of how the interval is computed.

  2. NAIVE PAIRWISE INFERENCE. Repetition pairs within a task share the task's
     latent difficulty, so they are not independent observations. Treating the
     n_pairs comparisons as independent understates the variance and produces
     intervals that are too narrow, i.e. under-cover.

Three methods are compared on identical simulated data:

  A  proposed   -- off-diagonal W_A, task-level (clustered) bootstrap
  B  naive      -- off-diagonal W_A, pairs resampled as if independent
  C  diagonal   -- self-pairs INCLUDED in W_A, task-level bootstrap
                   (same clustering as A, isolating the point-estimate bias)

Generator
---------
Binary agreement outcomes with a task-level random effect, so the population
W_A, C_AB and Delta are computable in closed form from the parameters rather
than estimated from a pilot run:

    task t draws a SHARED difficulty  s_t ~ Uniform(-h, h)
    and two INDEPENDENT property offsets  e_t^w, e_t^c ~ Uniform(-h, h)

    within-incumbent pair agrees  w.p. clip(p_w + s_t + e_t^w)
    cross-model pair agrees       w.p. clip(p_c + s_t + e_t^c)

The shared component s_t is what makes pairs within a task dependent (the
failure mode method B ignores). The independent components e_t are essential
for realism: if the task effect were shared ONLY, W_A and C_AB would move in
lockstep and their difference would be far more stable than in the observed
data, making a correct bootstrap appear to over-cover. The real study shows
per-task W_A and C_AB varying substantially relative to each other.

All three components are symmetric with mean 0 and the clip is inactive across
the parameter ranges used, so E[W_A] = p_w and E[C_AB] = p_c and the population
Delta is p_c - p_w exactly. Scenarios are fixed BEFORE any method was run.

No network, no model calls. Deterministic given --seed.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

INCUMBENT_REPS = 8      # frozen study design
CANDIDATE_REPS = 5      # frozen study design
CI_LEVEL = 95.0


@dataclass(frozen=True)
class Scenario:
    name: str
    n_tasks: int
    p_w: float           # population within-incumbent agreement
    p_c: float           # population cross-model agreement
    heterogeneity: float  # half-width of the task random effect

    @property
    def true_delta(self) -> float:
        return self.p_c - self.p_w


#: Pre-specified grid, fixed before any method was evaluated:
#:   - two task counts spanning the study's stress (20) and primary (60) sets
#:   - three effect sizes: null, moderate, large
#:   - three heterogeneity levels, ALL NON-ZERO
#:
#: Heterogeneity is deliberately never 0. At h = 0 there is no within-task
#: dependence to ignore, so naive pairwise inference is correct by construction
#: and the comparison is vacuous. Real tasks differ in difficulty; h in
#: [0.10, 0.25] brackets the per-task spread observed in the study data.
SCENARIOS: list[Scenario] = [
    Scenario(f"T{t}_pw{pw}_pc{pc}_h{h}", t, pw, pc, h)
    for t, (pw, pc), h in itertools.product(
        (20, 60),
        ((0.85, 0.85), (0.85, 0.70), (0.85, 0.50)),
        (0.10, 0.175, 0.25),
    )
]


def simulate_dataset(rng: np.random.Generator, sc: Scenario):
    """One synthetic experiment.

    Returns (within, cross): per-task matrices of binary agreement outcomes.
    `within` is n_inc x n_inc with the diagonal filled by self-comparisons
    (always 1.0, as a real self-comparison would be); `cross` is n_inc x n_cand.
    """
    within, cross = [], []
    h = sc.heterogeneity
    for _ in range(sc.n_tasks):
        shared = rng.uniform(-h, h)                  # task difficulty
        off_w = rng.uniform(-h, h)                   # independent W_A offset
        off_c = rng.uniform(-h, h)                   # independent C_AB offset
        pw = float(np.clip(sc.p_w + shared + off_w, 0.0, 1.0))
        pc = float(np.clip(sc.p_c + shared + off_c, 0.0, 1.0))

        w = np.eye(INCUMBENT_REPS)          # diagonal = self-comparison = 1.0
        iu = np.triu_indices(INCUMBENT_REPS, k=1)
        draws = rng.binomial(1, pw, size=len(iu[0])).astype(float)
        w[iu] = draws
        w[(iu[1], iu[0])] = draws           # symmetric
        within.append(w)

        cross.append(rng.binomial(1, pc,
                                  size=(INCUMBENT_REPS, CANDIDATE_REPS)).astype(float))
    return within, cross


# ---------------- point estimators ----------------

def _offdiag_mean(mats: list[np.ndarray], keeps: list | None = None) -> float:
    """Mean over strictly off-diagonal entries.

    Under a stage-2 resample the same original repetition can be drawn twice;
    the resulting (i,i) comparison is a self-comparison scoring 1.0 by
    construction. Because the resampled matrix is indexed by ORIGINAL rows,
    those duplicates land on the diagonal of the reindexed matrix only when the
    positions coincide, so the k=1 mask alone is not sufficient. Callers pass
    the drawn row indices so genuine duplicates are excluded.
    """
    tot = n = 0.0
    for k, m in enumerate(mats):
        iu = np.triu_indices(m.shape[0], k=1)
        vals = m[iu]
        if keeps is not None:
            vals = vals[keeps[k][iu]]
        tot += float(vals.sum()); n += vals.size
    return tot / n if n else float("nan")


def _withdiag_mean(mats: list[np.ndarray]) -> float:
    """Includes the diagonal self-comparisons. Deliberately biased."""
    tot = n = 0.0
    for m in mats:
        iu = np.triu_indices(m.shape[0], k=0)   # k=0 keeps the diagonal
        tot += float(m[iu].sum()); n += len(iu[0])
    return tot / n if n else float("nan")


def _flat_mean(mats: list[np.ndarray]) -> float:
    tot = n = 0.0
    for m in mats:
        tot += float(m.sum()); n += m.size
    return tot / n if n else float("nan")


def delta_offdiag(within, cross, keeps=None) -> float:
    return _flat_mean(cross) - _offdiag_mean(within, keeps)


def delta_withdiag(within, cross, keeps=None) -> float:
    """Deliberately keeps self-comparisons: the contaminated comparator."""
    return _flat_mean(cross) - _withdiag_mean(within)


# ---------------- interval methods ----------------

def ci_cluster_bootstrap(within, cross, rng, reps, point_fn,
                         two_stage: bool = True) -> tuple[float, float]:
    """Two-level bootstrap matching the paper's estimator.

    Stage 1 resamples TASKS with replacement (the cluster level). Stage 2
    resamples REPETITIONS with replacement inside each drawn task.

    Both stages are required. Resampling tasks alone reuses each task's fixed
    outcome matrix, so the within-task sampling noise — which dominates the
    variance of Delta when the task effect shifts W_A and C_AB together and
    partially cancels in their difference — is never regenerated, and the
    intervals come out too narrow.
    """
    n = len(within)
    draws = np.empty(reps)
    for b in range(reps):
        idx = rng.integers(0, n, n)
        if not two_stage:
            draws[b] = point_fn([within[i] for i in idx], [cross[i] for i in idx])
            continue
        ws, cs, keeps = [], [], []
        for i in idx:
            w, c = within[i], cross[i]
            ri = rng.integers(0, w.shape[0], w.shape[0])   # incumbent reps
            cj = rng.integers(0, c.shape[1], c.shape[1])   # candidate reps
            ws.append(w[np.ix_(ri, ri)])
            cs.append(c[np.ix_(ri, cj)])
            # a resampled pair is a genuine self-comparison when the SAME
            # original repetition was drawn twice; drop those, per the paper's
            # distinct-repetitions rule
            keeps.append(ri[:, None] != ri[None, :])
        draws[b] = point_fn(ws, cs, keeps)
    return (float(np.percentile(draws, (100 - CI_LEVEL) / 2)),
            float(np.percentile(draws, 100 - (100 - CI_LEVEL) / 2)))


def ci_naive_pairwise(within, cross, rng, reps) -> tuple[float, float]:
    """Resample individual PAIR observations as if independent.

    This is the error the paper warns about: the n_pairs comparisons are
    treated as n_pairs independent data points, ignoring that pairs inside a
    task share that task's latent difficulty.
    """
    wv = np.concatenate([m[np.triu_indices(m.shape[0], k=1)] for m in within])
    cv = np.concatenate([m.ravel() for m in cross])
    draws = np.empty(reps)
    for b in range(reps):
        draws[b] = (cv[rng.integers(0, cv.size, cv.size)].mean()
                    - wv[rng.integers(0, wv.size, wv.size)].mean())
    return (float(np.percentile(draws, (100 - CI_LEVEL) / 2)),
            float(np.percentile(draws, 100 - (100 - CI_LEVEL) / 2)))


METHODS = ("A_proposed_offdiag_cluster",
           "B_naive_offdiag_pairwise",
           "C_diagonal_contaminated_cluster")


def run_scenario(sc: Scenario, n_sim: int, boot_reps: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    acc = {m: {"est": [], "cover": [], "width": []} for m in METHODS}

    for _ in range(n_sim):
        within, cross = simulate_dataset(rng, sc)
        d_off = delta_offdiag(within, cross)
        d_dia = delta_withdiag(within, cross)

        lo, hi = ci_cluster_bootstrap(within, cross, rng, boot_reps, delta_offdiag)
        _record(acc["A_proposed_offdiag_cluster"], d_off, lo, hi, sc.true_delta)

        lo, hi = ci_naive_pairwise(within, cross, rng, boot_reps)
        _record(acc["B_naive_offdiag_pairwise"], d_off, lo, hi, sc.true_delta)

        lo, hi = ci_cluster_bootstrap(within, cross, rng, boot_reps, delta_withdiag)
        _record(acc["C_diagonal_contaminated_cluster"], d_dia, lo, hi, sc.true_delta)

    rows = []
    for m in METHODS:
        est = np.array(acc[m]["est"]); cov = np.array(acc[m]["cover"], dtype=float)
        coverage = float(cov.mean())
        rows.append({
            "scenario": sc.name, "n_tasks": sc.n_tasks,
            "p_w": sc.p_w, "p_c": sc.p_c, "heterogeneity": sc.heterogeneity,
            "true_delta": round(sc.true_delta, 6),
            "method": m,
            "mean_estimate": round(float(est.mean()), 6),
            "bias": round(float(est.mean() - sc.true_delta), 6),
            "empirical_se": round(float(est.std(ddof=1)), 6),
            "coverage_95": round(coverage, 4),
            "noncoverage_rate": round(1.0 - coverage, 4),
            "mc_se_coverage": round(float(np.sqrt(coverage * (1 - coverage) / len(cov))), 4),
            "mean_ci_width": round(float(np.mean(acc[m]["width"])), 6),
            "n_sim": len(cov),
        })
    return rows


def _record(store, est, lo, hi, truth):
    store["est"].append(est)
    store["cover"].append(bool(lo <= truth <= hi))
    store["width"].append(hi - lo)


def write_csv(rows, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def summarise(rows, n_sim, boot_reps, seed, runtime_s) -> str:
    import statistics as st
    by = {m: [r for r in rows if r["method"] == m] for m in METHODS}
    L = ["# Bootstrap coverage simulation", "",
         f"- simulation datasets per scenario: **{n_sim}**",
         f"- bootstrap replicates per interval: **{boot_reps}**",
         f"- scenarios: **{len(SCENARIOS)}**  (2 task counts x 3 effects x 2 heterogeneity)",
         f"- seed: `{seed}`", f"- runtime: {runtime_s:.1f} s",
         f"- Monte Carlo SE on a coverage near 0.95: "
         f"{np.sqrt(0.95*0.05/n_sim):.4f}", "",
         "All scenarios were fixed before any method was evaluated.", "",
         "## Aggregate across all scenarios", "",
         "| method | mean bias | mean 95% coverage | mean CI width |",
         "|---|---|---|---|"]
    for m in METHODS:
        L.append("| %s | %+.4f | %.3f | %.4f |" % (
            m, st.mean(r["bias"] for r in by[m]),
            st.mean(r["coverage_95"] for r in by[m]),
            st.mean(r["mean_ci_width"] for r in by[m])))
    L += ["", "## Expected qualitative checks", ""]
    bias_c = st.mean(r["bias"] for r in by["C_diagonal_contaminated_cluster"])
    bias_a = st.mean(r["bias"] for r in by["A_proposed_offdiag_cluster"])
    cov_a = st.mean(r["coverage_95"] for r in by["A_proposed_offdiag_cluster"])
    cov_b = st.mean(r["coverage_95"] for r in by["B_naive_offdiag_pairwise"])
    # highest heterogeneity level actually present in these rows
    hmax = max(r["heterogeneity"] for r in rows)
    het_rows = [r for r in by["B_naive_offdiag_pairwise"]
                if r["heterogeneity"] == hmax]
    cov_b_het = st.mean(r["coverage_95"] for r in het_rows) if het_rows else float("nan")
    checks = [
        ("diagonal contamination biases Delta downward",
         bias_c < bias_a - 1e-6, f"C bias {bias_c:+.4f} vs A bias {bias_a:+.4f}"),
        ("naive pairwise inference under-covers relative to clustered",
         cov_b < cov_a, f"B coverage {cov_b:.3f} vs A coverage {cov_a:.3f}"),
        ("naive under-coverage worsens with heterogeneity",
         cov_b_het <= cov_b + 1e-9,
         f"B coverage at h={hmax}: {cov_b_het:.3f} vs overall {cov_b:.3f}"),
        ("task-aware off-diagonal inference is near nominal",
         abs(cov_a - 0.95) < 0.05, f"A coverage {cov_a:.3f} (nominal 0.95)"),
    ]
    for name, ok, detail in checks:
        L.append(f"- {'**CONFIRMED**' if ok else '**NOT CONFIRMED**'}: {name} — {detail}")
    L += ["", "## Per-scenario detail", "",
          "| scenario | method | bias | coverage | width |", "|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %+.4f | %.3f | %.4f |" % (
            r["scenario"], r["method"], r["bias"], r["coverage_95"], r["mean_ci_width"]))
    return "\n".join(L) + "\n"


def plot(rows, out_pdf: Path, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    colors = {"A_proposed_offdiag_cluster": "#2980b9",
              "B_naive_offdiag_pairwise": "#e67e22",
              "C_diagonal_contaminated_cluster": "#c0392b"}
    labels = {"A_proposed_offdiag_cluster": "A proposed\n(off-diag + cluster)",
              "B_naive_offdiag_pairwise": "B naive\n(pairs independent)",
              "C_diagonal_contaminated_cluster": "C diagonal\ncontaminated"}
    # derive from the rows actually produced, so a --scenarios subset plots too
    scen = list(dict.fromkeys(r["scenario"] for r in rows))
    x = np.arange(len(scen))

    for ax, key, title, ref in (
            (axes[0], "bias", "Bias of $\\hat\\Delta$", 0.0),
            (axes[1], "coverage_95", "95% CI coverage", 0.95),
            (axes[2], "mean_ci_width", "Mean CI width", None)):
        for i, m in enumerate(METHODS):
            vals = [next(r[key] for r in rows if r["scenario"] == s and r["method"] == m)
                    for s in scen]
            ax.bar(x + (i - 1) * 0.27, vals, 0.27, label=labels[m], color=colors[m])
        if ref is not None:
            ax.axhline(ref, color="black", linestyle="--", linewidth=1)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(x); ax.set_xticklabels(scen, rotation=90, fontsize=6)
        ax.grid(axis="y", alpha=0.3)
    axes[1].set_ylim(0, 1.05)
    axes[0].legend(fontsize=7, loc="best")
    fig.suptitle("Estimator bias and interval calibration across pre-specified scenarios",
                 fontsize=12)
    fig.tight_layout()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams["pdf.compression"] = 0
    fig.savefig(out_pdf, metadata={"CreationDate": None})
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260803)
    ap.add_argument("--n-sim", type=int, default=2000)
    ap.add_argument("--boot-reps", type=int, default=400)
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/bootstrap_coverage.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/bootstrap_coverage_summary.md")
    ap.add_argument("--pdf", type=Path, default=REPO / "figures/bootstrap_coverage.pdf")
    ap.add_argument("--png", type=Path, default=REPO / "figures/bootstrap_coverage.png")
    ap.add_argument("--scenarios", type=int, help="limit scenario count (smoke test)")
    args = ap.parse_args()

    scen = SCENARIOS[:args.scenarios] if args.scenarios else SCENARIOS
    t0 = time.time()
    rows = []
    for i, sc in enumerate(scen):
        # distinct, deterministic stream per scenario
        rows.extend(run_scenario(sc, args.n_sim, args.boot_reps, args.seed + 1000 * i))
        print(f"  scenario {i+1}/{len(scen)}: {sc.name}", flush=True)
    runtime = time.time() - t0

    write_csv(rows, args.csv)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(summarise(rows, args.n_sim, args.boot_reps,
                                      args.seed, runtime))
    plot(rows, args.pdf, args.png)
    print(json.dumps({"scenarios": len(scen), "rows": len(rows),
                      "n_sim": args.n_sim, "boot_reps": args.boot_reps,
                      "runtime_s": round(runtime, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
