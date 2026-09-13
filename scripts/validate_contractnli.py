#!/usr/bin/env python3
"""Validate a locally downloaded ContractNLI file before corpus construction.

Checks the file is the genuine official dataset with the expected shape, so a
truncated download, a wrong file, or a third-party mirror with a different
schema fails loudly here rather than silently producing a corpus.

    python scripts/validate_contractnli.py --source data/raw/contractnli/train.json

Exits non-zero on any hard failure. Reports soft observations separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}

#: The official release pairs every document with the SAME 17 hypotheses.
EXPECTED_HYPOTHESES = 17
#: Full corpus is 607 NDAs; a single split holds fewer.
EXPECTED_TOTAL_DOCS = 607
MIN_DOCS_FOR_CORPUS = 100   # need >=80 distinct docs, with headroom


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    default=Path("corpora/pipeline2/contractnli_validation.json"))
    args = ap.parse_args()

    hard: list[str] = []
    soft: list[str] = []

    if not args.source.exists():
        print(f"FAIL: {args.source} does not exist.\n"
              f"Accept the ToU and download from "
              f"https://stanfordnlp.github.io/contract-nli/ , then place the "
              f"file at that path. See data/raw/contractnli/README.md.")
        return 2

    try:
        raw = json.loads(args.source.read_text())
    except json.JSONDecodeError as e:
        print(f"FAIL: {args.source} is not valid JSON ({e}). "
              f"A truncated or partial download is the usual cause.")
        return 2

    # ---- top-level shape ------------------------------------------------
    if isinstance(raw, dict) and "documents" in raw:
        docs = raw["documents"]
        labels_meta = raw.get("labels", {})
    elif isinstance(raw, list):
        docs = raw
        labels_meta = {}
        soft.append("top level is a bare list; official releases wrap it in "
                    "{'documents': [...], 'labels': {...}}")
    else:
        print("FAIL: unrecognised structure. Expected an object with a "
              "'documents' key (official ContractNLI format).")
        return 2

    if not isinstance(docs, list) or not docs:
        hard.append("'documents' is empty or not a list")
        docs = []

    if labels_meta and len(labels_meta) != EXPECTED_HYPOTHESES:
        soft.append(f"{len(labels_meta)} hypotheses in 'labels' "
                    f"(official release has {EXPECTED_HYPOTHESES})")

    # ---- per-document shape ---------------------------------------------
    n_docs = len(docs)
    doc_ids: set[str] = set()
    label_counts: Counter = Counter()
    hyp_keys: Counter = Counter()
    ann_total = 0
    with_spans = 0
    span_oob = 0
    doc_lens: list[int] = []
    missing_fields: Counter = Counter()

    for d in docs:
        if not isinstance(d, dict):
            hard.append("a document entry is not an object")
            continue
        for f in ("id", "text", "spans", "annotation_sets"):
            if f not in d:
                missing_fields[f] += 1
        doc_ids.add(str(d.get("id")))
        text = d.get("text", "") or ""
        doc_lens.append(len(text))
        spans = d.get("spans", []) or []

        sets = d.get("annotation_sets", []) or []
        if not sets:
            continue
        anns = (sets[0] or {}).get("annotations", {}) or {}
        for hkey, ann in anns.items():
            ann_total += 1
            hyp_keys[hkey] += 1
            choice = (ann or {}).get("choice")
            label_counts[choice] += 1
            if choice not in VALID_LABELS:
                hard.append(f"invalid label {choice!r} on document {d.get('id')}")
            idxs = (ann or {}).get("spans", []) or []
            if idxs:
                with_spans += 1
                for i in idxs:
                    if not isinstance(i, int) or i < 0 or i >= len(spans):
                        span_oob += 1

    for f, n in missing_fields.items():
        hard.append(f"{n} documents missing required field {f!r}")
    if span_oob:
        hard.append(f"{span_oob} evidence-span indices out of range")
    if n_docs < MIN_DOCS_FOR_CORPUS:
        hard.append(f"only {n_docs} documents; need >= {MIN_DOCS_FOR_CORPUS} "
                    f"to draw 60 primary + 20 stress from distinct documents")
    if len(doc_ids) != n_docs:
        hard.append(f"duplicate document ids: {n_docs} docs, "
                    f"{len(doc_ids)} unique")
    for lbl in VALID_LABELS:
        if label_counts.get(lbl, 0) < 20:
            hard.append(f"only {label_counts.get(lbl, 0)} '{lbl}' annotations; "
                        f"need >= 20 per label for a balanced primary set")

    if n_docs > EXPECTED_TOTAL_DOCS:
        soft.append(f"{n_docs} documents exceeds the full-corpus count of "
                    f"{EXPECTED_TOTAL_DOCS}; is this really ContractNLI?")
    if len(hyp_keys) != EXPECTED_HYPOTHESES:
        soft.append(f"{len(hyp_keys)} distinct hypothesis keys "
                    f"(expected {EXPECTED_HYPOTHESES})")

    doc_lens.sort()
    report = {
        "source": str(args.source),
        "sha256": sha256(args.source),
        "size_bytes": args.source.stat().st_size,
        "n_documents": n_docs,
        "n_unique_document_ids": len(doc_ids),
        "n_annotations": ann_total,
        "n_annotations_with_evidence_spans": with_spans,
        "distinct_hypothesis_keys": len(hyp_keys),
        "label_distribution": dict(label_counts),
        "doc_chars": {
            "min": doc_lens[0] if doc_lens else 0,
            "median": doc_lens[len(doc_lens) // 2] if doc_lens else 0,
            "max": doc_lens[-1] if doc_lens else 0,
            "over_60k_chars": sum(1 for x in doc_lens if x > 60_000),
        },
        "hard_failures": hard,
        "soft_observations": soft,
        "status": "PASS" if not hard else "FAIL",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not hard else 1


if __name__ == "__main__":
    raise SystemExit(main())
