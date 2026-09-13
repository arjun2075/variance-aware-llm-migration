#!/usr/bin/env python3
"""Build the Pipeline 2 corpus from ContractNLI: 60 primary + 20 stress cases.

ContractNLI (https://stanfordnlp.github.io/contract-nli/) is CC BY 4.0, but the
download is gated behind a click-through Terms of Use. This script does NOT
download it. Point --source at a locally obtained copy of `train.json` /
`dev.json` once you have accepted the ToU.

Sampling
--------
Sampled at the DOCUMENT level, never at document x hypothesis. ContractNLI pairs
607 NDAs with the SAME 17 hypotheses, so doc x hypothesis pairs are strongly
correlated within a document; treating them as independent clusters would
understate bootstrap uncertainty. One hypothesis is selected per sampled
document, stratified across the three gold labels.

Gold handling
-------------
Gold labels and gold evidence spans are carried in the corpus for SCORING ONLY.
`inference_view()` produces the redacted record given to models, and
`test_p2_corpus.py` asserts no gold field survives into it. A leak here would
silently invalidate every correctness result in the study.

Fallback
--------
--synthetic builds a structurally identical fixture set so the mock dry run can
exercise the full orchestration before the real data is in place. Synthetic
records are marked `"synthetic_fixture": true` and MUST NOT be used for the
confirmatory run; the freeze check rejects them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

SEED = 20260803
LABELS = ["Entailment", "Contradiction", "NotMentioned"]
MAX_DOC_CHARS = 60_000   # ~15k tokens; keeps the context budget feasible


def inference_view(case: dict) -> dict:
    """The record a model may see. Gold fields are removed here, not hidden."""
    return {
        "task_id": case["task_id"],
        "document_id": case["document_id"],
        "document_text": case["document_text"],
        "hypothesis": case["hypothesis"],
        "label_options": LABELS,
    }


def _load_contractnli(source: Path) -> list[dict]:
    raw = json.loads(source.read_text())
    docs = raw["documents"] if isinstance(raw, dict) and "documents" in raw else raw
    labels_meta = raw.get("labels", {}) if isinstance(raw, dict) else {}
    out = []
    for d in docs:
        text = d.get("text", "")
        if not text or len(text) > MAX_DOC_CHARS:
            continue
        spans = d.get("spans", [])
        for hkey, ann in (d.get("annotation_sets", [{}])[0]
                          .get("annotations", {}) or {}).items():
            choice = ann.get("choice")
            if choice not in ("Entailment", "Contradiction", "NotMentioned"):
                continue
            span_idx = ann.get("spans", []) or []
            out.append({
                "document_id": str(d.get("id")),
                "document_text": text,
                "hypothesis_key": hkey,
                "hypothesis": (labels_meta.get(hkey, {}) or {}).get("hypothesis", hkey),
                "gold_label": choice,
                "gold_span_indices": span_idx,
                "gold_spans": [text[spans[i][0]:spans[i][1]]
                               for i in span_idx if i < len(spans)],
                "n_doc_chars": len(text),
            })
    return out


def _synthetic(n: int, rng: random.Random) -> list[dict]:
    clauses = [
        "The Receiving Party shall not disclose Confidential Information to any third party.",
        "This Agreement shall remain in effect for a period of three (3) years.",
        "Confidential Information does not include information already in the public domain.",
        "The Receiving Party may share Confidential Information with employees on a need-to-know basis.",
        "Upon termination, the Receiving Party shall return or destroy all Confidential Information.",
        "Neither party acquires any licence under any intellectual property right.",
        "The Receiving Party shall notify the Disclosing Party of any compelled disclosure.",
    ]
    hyps = [
        "The Receiving Party may share confidential information with its employees.",
        "The agreement expires after a fixed term.",
        "Publicly available information is excluded from confidentiality obligations.",
        "The Receiving Party must destroy confidential information on termination.",
        "The Receiving Party is granted a licence to the intellectual property.",
    ]
    out = []
    for i in range(n):
        k = rng.randint(4, 7)
        picked = rng.sample(clauses, k)
        text = "SYNTHETIC FIXTURE — NOT REAL CONTRACT TEXT\n\n" + "\n\n".join(
            f"{j+1}. {c}" for j, c in enumerate(picked))
        gold_i = rng.randrange(len(picked))
        out.append({
            "document_id": f"synthetic_nda_{i:03d}",
            "document_text": text,
            "hypothesis_key": f"synth_h{i%len(hyps)}",
            "hypothesis": hyps[i % len(hyps)],
            "gold_label": rng.choice(LABELS),
            "gold_span_indices": [gold_i],
            "gold_spans": [picked[gold_i]],
            "n_doc_chars": len(text),
            "synthetic_fixture": True,
        })
    return out


def select(pool: list[dict], n: int, rng: random.Random,
           exclude_docs: set[str]) -> list[dict]:
    """Pick n instances from n DISTINCT documents, stratified by gold label."""
    by_doc: dict[str, list[dict]] = {}
    for r in pool:
        if r["document_id"] in exclude_docs:
            continue
        by_doc.setdefault(r["document_id"], []).append(r)
    doc_ids = sorted(by_doc)
    rng.shuffle(doc_ids)

    per_label = n // len(LABELS)
    quota = {l: per_label for l in LABELS}
    for l in LABELS[: n - per_label * len(LABELS)]:
        quota[l] += 1

    chosen: list[dict] = []
    for doc in doc_ids:
        if len(chosen) >= n:
            break
        opts = [r for r in by_doc[doc] if quota.get(r["gold_label"], 0) > 0]
        if not opts:
            continue
        pick = rng.choice(opts)
        quota[pick["gold_label"]] -= 1
        chosen.append(pick)

    # top up if a label ran short (small or skewed pools)
    if len(chosen) < n:
        used = {c["document_id"] for c in chosen}
        for doc in doc_ids:
            if len(chosen) >= n:
                break
            if doc in used:
                continue
            chosen.append(rng.choice(by_doc[doc]))
    if len(chosen) < n:
        raise RuntimeError(f"only {len(chosen)}/{n} distinct documents available")
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path,
                    help="local ContractNLI train.json (after accepting the ToU)")
    ap.add_argument("--synthetic", action="store_true",
                    help="build structurally identical fixtures for the dry run")
    ap.add_argument("--out-dir", type=Path, default=Path("corpora/pipeline2"))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    if not args.source and not args.synthetic:
        ap.error("pass --source <contractnli json> or --synthetic")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    pool = (_synthetic(200, rng) if args.synthetic
            else _load_contractnli(args.source))
    if len(pool) < 80:
        raise RuntimeError(f"pool too small: {len(pool)}")

    primary = select(pool, 60, rng, exclude_docs=set())
    used = {c["document_id"] for c in primary}
    stress = select(pool, 20, rng, exclude_docs=used)

    report = {"seed": args.seed,
              "source": "synthetic_fixture" if args.synthetic else str(args.source),
              "is_synthetic_fixture": bool(args.synthetic),
              "sampling_unit": "document",
              "license": "CC BY 4.0 (ContractNLI); ToU accepted out of band",
              "gold_leakage_policy": (
                  "gold_label and gold_spans are stored for SCORING ONLY; "
                  "inference_view() strips them before any model sees a record")}

    for name, cases in (("primary", primary), ("stress", stress)):
        for i, c in enumerate(cases):
            c["task_id"] = f"p2_{name}_{i:03d}"
            c["partition"] = name
        path = args.out_dir / f"p2_{name}.jsonl"
        with path.open("w") as fh:
            for c in cases:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        dist: dict[str, int] = {}
        for c in cases:
            dist[c["gold_label"]] = dist.get(c["gold_label"], 0) + 1
        report[name] = {
            "path": str(path), "n": len(cases),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "distinct_documents": len({c["document_id"] for c in cases}),
            "gold_label_distribution": dist,
            "median_doc_chars": sorted(c["n_doc_chars"] for c in cases)[len(cases)//2],
            "max_doc_chars": max(c["n_doc_chars"] for c in cases),
        }
    report["primary_stress_document_overlap"] = len(
        {c["document_id"] for c in primary} & {c["document_id"] for c in stress})

    (args.out_dir / "p2_corpus_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
