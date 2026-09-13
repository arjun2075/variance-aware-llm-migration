# Verbatim-reuse check — Pipeline 1 prompts

**Date:** 2026-09-09 · **Verdict: PASS**

## What was checked

All four Pipeline 1 research prompts were compared against the historical
study's production synthesis prompt using 6-gram shingle overlap.

**The comparison ran entirely outside this repository**, against the artifact in
its read-only backup. Only the verdict is recorded here. The proprietary text
was never copied into this repository, and the automated guard
(`tests/test_no_proprietary_content.py`) independently asserts that none of its
distinctive phrasing appears in the tree.

## Result

| Prompt | 6-grams | Shared with production | Fraction |
|---|---|---|---|
| stage1_pr_signal.md | 141 | 1 | 0.71% |
| stage2_review_signal.md | 102 | 0 | 0.00% |
| stage3_synthesis.md | 196 | 0 | 0.00% |
| stage4_deepen.md | 121 | 0 | 0.00% |

The production prompt contains 787 distinct 6-grams.

The single shared 6-gram is **"no prose outside the json"** — a generic
JSON-output instruction, not proprietary content.

**Conclusion:** no meaningful verbatim reuse. The Pipeline 1 prompts are newly
authored and share only their structural role — a four-stage analyse → analyse →
synthesise → extend chain — with the pipeline that motivated the study. That
structural similarity is the object of study and is stated openly in the paper;
it is not inherited text.

These prompts are released in full with the paper.
