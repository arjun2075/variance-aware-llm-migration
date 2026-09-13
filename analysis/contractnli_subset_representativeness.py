#!/usr/bin/env python3
"""Is the frozen 60-task P2 primary subset atypical of its eligible pool?

Compares the selected 60 tasks against the eligible ContractNLI sampling frame
they were drawn from, reconstructed with the SAME eligibility rules the frozen
build script used:

  * document text non-empty and <= MAX_DOC_CHARS (60,000)
  * annotation choice in {Entailment, Contradiction, NotMentioned}

The 60 tasks are NOT resampled or modified — they are read as frozen.

*** THE LABEL DISTRIBUTION IS BALANCED BY DESIGN. ***
The frozen sampler stratifies to 20/20/20 across the three gold labels. A
difference from the natural ContractNLI label distribution is therefore an
intended property of the design, not evidence of a sampling defect. It is
reported for completeness and explicitly excluded from any "atypical" judgement.

Variables compared:
  categorical  gold label (by design), evidence-present vs none
  continuous   document length, evidence-span count, evidence-span char length,
               hypothesis frequency

For continuous variables we report both sets' mean/median, the standardized
mean difference (Cohen's d with a pooled SD), and a quantile comparison. With
n=60 against a pool in the thousands, significance tests answer the wrong
question, so effect sizes and descriptive comparisons lead.

No model calls, no network.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAX_DOC_CHARS = 60_000        # frozen eligibility rule
VALID_LABELS = ("Entailment", "Contradiction", "NotMentioned")
#: SMD magnitudes conventionally read as negligible / small / moderate
SMD_NEGLIGIBLE, SMD_SMALL = 0.10, 0.30


def eligible_pool(source: Path) -> list[dict]:
    """Rebuild the sampling frame under the frozen eligibility rules."""
    raw = json.loads(source.read_text())
    docs = raw["documents"] if isinstance(raw, dict) and "documents" in raw else raw
    meta = raw.get("labels", {}) if isinstance(raw, dict) else {}
    out = []
    for d in docs:
        text = d.get("text", "") or ""
        if not text or len(text) > MAX_DOC_CHARS:
            continue
        spans = d.get("spans", []) or []
        sets = d.get("annotation_sets", []) or [{}]
        for hkey, ann in ((sets[0] or {}).get("annotations", {}) or {}).items():
            choice = (ann or {}).get("choice")
            if choice not in VALID_LABELS:
                continue
            idx = (ann or {}).get("spans", []) or []
            out.append({
                "document_id": str(d.get("id")),
                "hypothesis_key": hkey,
                "gold_label": choice,
                "n_doc_chars": len(text),
                "n_evidence_spans": len(idx),
                "has_evidence": bool(idx),
                "evidence_chars": sum(
                    (spans[i][1] - spans[i][0]) for i in idx
                    if isinstance(i, int) and 0 <= i < len(spans)),
            })
    return out


def selected_set(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        out.append({
            "document_id": c["document_id"],
            "hypothesis_key": c.get("hypothesis_key", ""),
            "gold_label": c["gold_label"],
            "n_doc_chars": c["n_doc_chars"],
            "n_evidence_spans": len(c.get("gold_span_indices", []) or []),
            "has_evidence": bool(c.get("gold_span_indices")),
            "evidence_chars": sum(len(s) for s in (c.get("gold_spans") or [])),
        })
    return out


def smd(a: list[float], b: list[float]) -> float:
    """Standardized mean difference (selected - pool), pooled SD."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    sa, sb = st.stdev(a), st.stdev(b)
    pooled = math.sqrt(((len(a) - 1) * sa ** 2 + (len(b) - 1) * sb ** 2)
                       / (len(a) + len(b) - 2))
    return (st.mean(a) - st.mean(b)) / pooled if pooled else 0.0


def quantiles(v: list[float]) -> dict:
    s = sorted(v)
    def q(p):
        if not s:
            return float("nan")
        i = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
        return float(s[i])
    return {"p10": q(0.10), "p25": q(0.25), "p50": q(0.50),
            "p75": q(0.75), "p90": q(0.90)}


def interpret(d: float) -> str:
    a = abs(d)
    if math.isnan(a):
        return "uncomputable"
    if a < SMD_NEGLIGIBLE:
        return "negligible"
    if a < SMD_SMALL:
        return "small"
    return "moderate_or_larger"


def continuous_rows(sel, pool) -> list[dict]:
    rows = []
    for var in ("n_doc_chars", "n_evidence_spans", "evidence_chars"):
        a = [float(r[var]) for r in sel]
        b = [float(r[var]) for r in pool]
        d = smd(a, b)
        qa, qb = quantiles(a), quantiles(b)
        rows.append({
            "variable": var, "type": "continuous",
            "by_design": False,
            "selected_n": len(a), "pool_n": len(b),
            "selected_mean": round(st.mean(a), 4),
            "pool_mean": round(st.mean(b), 4),
            "selected_median": round(st.median(a), 4),
            "pool_median": round(st.median(b), 4),
            "standardized_mean_difference": round(d, 4),
            "smd_interpretation": interpret(d),
            "selected_quantiles": json.dumps({k: round(v, 1) for k, v in qa.items()}),
            "pool_quantiles": json.dumps({k: round(v, 1) for k, v in qb.items()}),
        })
    return rows


def categorical_rows(sel, pool) -> list[dict]:
    rows = []
    for var, by_design in (("gold_label", True), ("has_evidence", False)):
        levels = sorted({str(r[var]) for r in sel} | {str(r[var]) for r in pool})
        for lv in levels:
            ps = sum(1 for r in sel if str(r[var]) == lv) / len(sel)
            pp = sum(1 for r in pool if str(r[var]) == lv) / len(pool)
            rows.append({
                "variable": f"{var}={lv}", "type": "categorical",
                "by_design": by_design,
                "selected_n": len(sel), "pool_n": len(pool),
                "selected_proportion": round(ps, 4),
                "pool_proportion": round(pp, 4),
                "absolute_pp_difference": round(100 * abs(ps - pp), 2),
            })
    return rows


def hypothesis_rows(sel, pool) -> list[dict]:
    """Hypothesis coverage: how many distinct hypotheses the subset touches."""
    hs, hp = {r["hypothesis_key"] for r in sel}, {r["hypothesis_key"] for r in pool}
    return [{
        "variable": "hypothesis_coverage", "type": "coverage", "by_design": False,
        "selected_n": len(sel), "pool_n": len(pool),
        "selected_distinct_hypotheses": len(hs),
        "pool_distinct_hypotheses": len(hp),
        "coverage_fraction": round(len(hs) / len(hp), 4) if hp else float("nan"),
        "max_selected_per_hypothesis": max(
            sum(1 for r in sel if r["hypothesis_key"] == h) for h in hs) if hs else 0,
    }]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
                    default=REPO / "data/raw/contractnli/train.json")
    ap.add_argument("--selected", type=Path,
                    default=REPO / "corpora/pipeline2/p2_primary.jsonl")
    ap.add_argument("--csv", type=Path,
                    default=REPO / "results/strengthening/contractnli_subset_representativeness.csv")
    ap.add_argument("--summary", type=Path,
                    default=REPO / "results/strengthening/contractnli_subset_representativeness_summary.md")
    args = ap.parse_args()

    if not args.source.exists():
        print(f"error: ContractNLI source not found at {args.source}. "
              f"It is gitignored; see docs/P2_CONTRACTNLI_INSTALL.md.")
        return 2

    sel = selected_set(args.selected)
    pool = eligible_pool(args.source)
    rows = (categorical_rows(sel, pool) + continuous_rows(sel, pool)
            + hypothesis_rows(sel, pool))

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with args.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in keys} for r in rows])
    args.summary.write_text(summarise(rows, sel, pool))
    cont = [r for r in rows if r["type"] == "continuous"]
    print(json.dumps({
        "selected": len(sel), "eligible_pool": len(pool),
        "max_abs_smd": round(max(abs(r["standardized_mean_difference"])
                                 for r in cont), 4),
        "non_negligible_continuous": [
            r["variable"] for r in cont
            if r["smd_interpretation"] != "negligible"],
    }, indent=2))
    return 0


def summarise(rows, sel, pool) -> str:
    cont = [r for r in rows if r["type"] == "continuous"]
    cat = [r for r in rows if r["type"] == "categorical"]
    cov = [r for r in rows if r["type"] == "coverage"][0]
    L = ["# ContractNLI subset representativeness", "",
         f"- selected (frozen P2 primary): **{len(sel)}** tasks",
         f"- eligible pool under the frozen rules: **{len(pool)}** instances",
         f"- eligibility: non-empty document text <= {MAX_DOC_CHARS:,} chars, "
         f"gold label in {VALID_LABELS}", "",
         "The 60 frozen tasks were not resampled or modified.", "",
         "## The label balance is BY DESIGN", "",
         "The frozen sampler stratifies to **20/20/20** across the three gold",
         "labels. Any difference from ContractNLI's natural label distribution",
         "is an intended property of the design, **not** evidence of a sampling",
         "bug. Those rows are marked `by_design=True` and are excluded from the",
         "question of whether the subset is atypical.", "",
         "## Categorical variables", "",
         "| variable | by design | selected | pool | abs. pp difference |",
         "|---|---|---|---|---|"]
    for r in cat:
        L.append(f'| {r["variable"]} | {"YES" if r["by_design"] else "no"} | '
                 f'{r["selected_proportion"]:.3f} | {r["pool_proportion"]:.3f} | '
                 f'{r["absolute_pp_difference"]:.2f} pp |')
    L += ["", "## Continuous variables", "",
          "| variable | selected mean | pool mean | selected median | pool median "
          "| SMD | reading |", "|---|---|---|---|---|---|---|"]
    for r in cont:
        L.append(f'| {r["variable"]} | {r["selected_mean"]:.1f} | '
                 f'{r["pool_mean"]:.1f} | {r["selected_median"]:.1f} | '
                 f'{r["pool_median"]:.1f} | {r["standardized_mean_difference"]:+.3f} '
                 f'| {r["smd_interpretation"]} |')
    L += ["", "### Quantile comparison", "",
          "| variable | set | p10 | p25 | p50 | p75 | p90 |", "|---|---|---|---|---|---|---|"]
    for r in cont:
        for tag, key in (("selected", "selected_quantiles"), ("pool", "pool_quantiles")):
            q = json.loads(r[key])
            L.append(f'| {r["variable"]} | {tag} | {q["p10"]:.0f} | {q["p25"]:.0f} '
                     f'| {q["p50"]:.0f} | {q["p75"]:.0f} | {q["p90"]:.0f} |')
    L += ["", "## Hypothesis coverage", "",
          f'- distinct hypotheses in the subset: **{cov["selected_distinct_hypotheses"]}** '
          f'of {cov["pool_distinct_hypotheses"]} '
          f'({cov["coverage_fraction"]:.1%})',
          f'- most tasks drawn from any single hypothesis: '
          f'**{cov["max_selected_per_hypothesis"]}**', "",
          "## Verdict", ""]
    bad = [r for r in cont if r["smd_interpretation"] == "moderate_or_larger"]
    small = [r for r in cont if r["smd_interpretation"] == "small"]
    if bad:
        L += [f"**{len(bad)} continuous variable(s) differ by a moderate or larger "
              f"standardized difference**: "
              + ", ".join(f'{r["variable"]} (SMD {r["standardized_mean_difference"]:+.3f})'
                          for r in bad) + ".", "",
              "This is a substantive difference and should be disclosed."]
    elif small:
        L += ["Aside from the intentional label balancing, no continuous variable "
              "differs by more than a *small* standardized difference: "
              + ", ".join(f'{r["variable"]} (SMD {r["standardized_mean_difference"]:+.3f})'
                          for r in small) + ".", "",
              "The subset is not obviously atypical of the eligible workload."]
    else:
        L += ["Aside from the intentional label balancing, every continuous "
              "variable differs by a **negligible** standardized difference "
              "(|SMD| < 0.10). The subset is not obviously atypical of the "
              "eligible ContractNLI workload."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
