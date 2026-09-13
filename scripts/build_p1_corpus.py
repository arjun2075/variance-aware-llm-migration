#!/usr/bin/env python3
"""Generate the Pipeline 1 corpus: 60 primary + 20 stress synthetic cases.

Design goal: GENUINE heterogeneity, not 60 paraphrases of one template. The
historical pilot used 8 cases built as 4 seniority levels x 4 archetypes; that
regular grid is exactly what the revision is trying to escape, because a
factorial of two factors produces correlated cases that inflate apparent
cluster independence.

Heterogeneity is therefore driven along SIX independent axes, sampled from a
seeded generator, with an explicit near-duplicate check afterwards:

  1. seniority band          (5 levels)
  2. work archetype          (8 archetypes, not 4)
  3. difficulty              (how clear-cut the evidence is)
  4. ambiguity               (how much the signals conflict)
  5. evidence volume         (short/medium/long inputs)
  6. evidence conflict mode  (which sources disagree, and how)

Stress cases are drawn from deliberately harder regions of the same space
(maximum ambiguity, contradictory sources, sparse or overwhelming evidence) and
are frozen SEPARATELY. They are never merged into the primary set and are never
used to rescue an inconclusive primary result.

NO REAL PERSONNEL DATA. Every field is synthetic and generated here. No company
name, no production identifier, no real person.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

SEED = 20260803

SENIORITY = ["early_career", "mid_level", "senior", "staff", "principal"]

ARCHETYPES = [
    "high_volume_low_review",
    "mentor_heavy",
    "incident_heavy",
    "low_volume_high_impact",
    "migration_specialist",      # long-running refactor work
    "cross_team_integrator",     # coordination-heavy, diffuse output
    "prototype_explorer",        # high churn, much discarded work
    "reliability_steward",       # invisible prevention work
]

DIFFICULTY = ["clear_cut", "moderate", "hard", "very_hard"]
AMBIGUITY = ["low", "medium", "high"]
VOLUME = ["sparse", "medium", "rich", "overwhelming"]

CONFLICT_MODES = [
    "none",
    "velocity_vs_quality",        # ships fast, defects follow
    "peer_vs_metrics",            # colleagues praise, numbers are flat
    "self_vs_observed",           # self-report diverges from artifacts
    "recent_vs_historical",       # trend reverses mid-period
    "breadth_vs_depth",           # many small items vs one deep item
    "output_vs_enablement",       # low personal output, high team multiplier
]

# Weighted so the primary set is dominated by realistic mid-range cases while
# still covering the tails; the stress set inverts this.
PRIMARY_W = {
    "difficulty": [0.30, 0.35, 0.25, 0.10],
    "ambiguity": [0.35, 0.40, 0.25],
    "volume": [0.20, 0.35, 0.35, 0.10],
}
STRESS_W = {
    "difficulty": [0.00, 0.10, 0.40, 0.50],
    "ambiguity": [0.00, 0.20, 0.80],
    "volume": [0.35, 0.10, 0.15, 0.40],
}


def _metrics(rng: random.Random, seniority: str, archetype: str,
             volume: str) -> dict:
    """Synthetic activity metrics, shaped by archetype and volume."""
    scale = {"sparse": 0.35, "medium": 1.0, "rich": 1.8, "overwhelming": 3.2}[volume]
    base = {
        "high_volume_low_review": dict(prs=18, reviews=3, points=28, incidents=1),
        "mentor_heavy": dict(prs=6, reviews=24, points=14, incidents=0),
        "incident_heavy": dict(prs=7, reviews=6, points=12, incidents=9),
        "low_volume_high_impact": dict(prs=4, reviews=7, points=22, incidents=1),
        "migration_specialist": dict(prs=11, reviews=5, points=34, incidents=2),
        "cross_team_integrator": dict(prs=8, reviews=15, points=18, incidents=3),
        "prototype_explorer": dict(prs=22, reviews=4, points=9, incidents=0),
        "reliability_steward": dict(prs=9, reviews=11, points=16, incidents=6),
    }[archetype]
    lvl = 1.0 + 0.12 * SENIORITY.index(seniority)
    out = {}
    for k, v in base.items():
        jitter = rng.uniform(0.75, 1.25)
        out[k] = max(0, int(round(v * scale * lvl * jitter)))
    out["test_coverage_pct"] = int(rng.triangular(28, 92, 68))
    out["self_merge_rate_pct"] = int(rng.triangular(0, 80, 22))
    out["median_review_latency_h"] = round(rng.triangular(1, 96, 14), 1)
    return out


def _baselines(rng: random.Random, metrics: dict) -> dict:
    """Team baselines, so the model can be asked to compare against something."""
    return {
        f"team_median_{k}": max(0, int(round(v * rng.uniform(0.6, 1.2))))
        for k, v in metrics.items() if isinstance(v, int)
    }


def _conflict_notes(rng: random.Random, mode: str) -> list[str]:
    return {
        "none": [],
        "velocity_vs_quality": [
            "Delivery volume is in the top quartile for the team.",
            "Three of the last eight merged changes required follow-up fixes within a week.",
        ],
        "peer_vs_metrics": [
            "Two peers independently described this person as the one they go to when stuck.",
            "Recorded output metrics sit near the team median with no upward trend.",
        ],
        "self_vs_observed": [
            "Self-assessment claims ownership of the caching redesign.",
            "Artifact history shows the redesign was authored by another contributor; this person reviewed it.",
        ],
        "recent_vs_historical": [
            "First half of the period shows sustained high output.",
            "Second half shows a marked decline with no stated reason.",
        ],
        "breadth_vs_depth": [
            "Contributed to eleven distinct components.",
            "No single contribution exceeded a two-day effort estimate.",
        ],
        "output_vs_enablement": [
            "Personal merged-change count is the lowest on the team.",
            "Unblocked four colleagues on separate occasions, each recorded in review threads.",
        ],
    }[mode]


def _make_case(rng: random.Random, idx: int, partition: str) -> dict:
    w = PRIMARY_W if partition == "primary" else STRESS_W
    seniority = rng.choice(SENIORITY)
    archetype = rng.choice(ARCHETYPES)
    difficulty = rng.choices(DIFFICULTY, weights=w["difficulty"])[0]
    ambiguity = rng.choices(AMBIGUITY, weights=w["ambiguity"])[0]
    volume = rng.choices(VOLUME, weights=w["volume"])[0]
    conflict = (rng.choice(CONFLICT_MODES[1:]) if partition == "stress"
                else rng.choice(CONFLICT_MODES))
    metrics = _metrics(rng, seniority, archetype, volume)
    return {
        "task_id": f"p1_{partition}_{idx:03d}",
        "partition": partition,
        "axes": {
            "seniority": seniority,
            "archetype": archetype,
            "difficulty": difficulty,
            "ambiguity": ambiguity,
            "evidence_volume": volume,
            "conflict_mode": conflict,
        },
        "subject": {
            "label": f"Synthetic Contributor {partition[0].upper()}{idx:03d}",
            "seniority_band": seniority,
            "period": "synthetic review period",
        },
        "metrics": metrics,
        "baselines": _baselines(rng, metrics),
        "narrative_signals": _conflict_notes(rng, conflict),
        "synthetic": True,
    }


def _signature(case: dict) -> tuple:
    """Coarse fingerprint used for the near-duplicate check."""
    a = case["axes"]
    return (a["seniority"], a["archetype"], a["difficulty"], a["ambiguity"],
            a["evidence_volume"], a["conflict_mode"])


def build(partition: str, n: int, rng: random.Random) -> list[dict]:
    """Sample n cases, rejecting exact axis-signature duplicates."""
    cases, seen, guard = [], set(), 0
    while len(cases) < n and guard < n * 200:
        guard += 1
        c = _make_case(rng, len(cases), partition)
        sig = _signature(c)
        if sig in seen:
            continue
        seen.add(sig)
        c["task_id"] = f"p1_{partition}_{len(cases):03d}"
        cases.append(c)
    if len(cases) < n:
        raise RuntimeError(
            f"only generated {len(cases)}/{n} distinct {partition} cases; "
            f"widen the axis space rather than lowering the bar")
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("corpora/pipeline1"))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    primary = build("primary", 60, rng)
    stress = build("stress", 20, rng)

    # Primary and stress must not overlap.
    overlap = {_signature(c) for c in primary} & {_signature(c) for c in stress}

    report = {}
    for name, cases in (("primary", primary), ("stress", stress)):
        path = args.out_dir / f"p1_{name}.jsonl"
        with path.open("w") as fh:
            for c in cases:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        axes = {k: {} for k in cases[0]["axes"]}
        for c in cases:
            for k, v in c["axes"].items():
                axes[k][v] = axes[k].get(v, 0) + 1
        report[name] = {
            "path": str(path), "n": len(cases), "sha256": digest,
            "distinct_axis_signatures": len({_signature(c) for c in cases}),
            "axis_coverage": axes,
        }
    report["primary_stress_signature_overlap"] = len(overlap)
    report["seed"] = args.seed
    (args.out_dir / "p1_corpus_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
