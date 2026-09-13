# tse-submission-v1 — public reproducibility artifact

Public artifact for **"Variance-Aware Regression Testing for Model Migration in
Compound LLM Pipelines"** (IEEE TSE submission).

Scientific analysis frozen at `3652060`. Nothing in this release changes a
reported result.

## What you can do with this

**Reproduce every reported statistic — no API keys, no model calls, no cost.**
All figures, tables and intervals are recomputed from the included ledger of
20,160 recorded model calls. `pytest` and the analysis scripts run offline
(one optional embedding-model download).

Re-executing the model calls is **not** required to verify any claim, and is
not expected to reproduce the same numbers — run-to-run variability is the
paper's subject. To try it, supply your own provider endpoints and credentials
and implement a `ProviderAdapter`.

## Contents

- `results/run/calls.jsonl` — the full confirmatory ledger (20,160 calls)
- `results/analysis/`, `results/strengthening/` — the authoritative analyses
- `corpora/`, `prompts/`, `protocol/` — frozen inputs and the protocol lock
- `analysis/vamigrate.py` — standalone CLI for the pairwise estimand
- `figures/` (14), 10 result tables, and the three study reports

## Verification

- **459 tests pass** from a clean clone
- primary analysis reproduces **bit-for-bit** (`pairwise_results.json` →
  `2195d0d414409db0...`)
- `PUBLIC_RELEASE=1` safety scan: **29 passed**

## Scope and exclusions

The confirmatory runs were executed through a managed execution path operated
by the author's employer. **Execution-infrastructure identifiers were removed
because they are not needed to reproduce any analysis**; neutral terminology
(`managed_execution_path`) is used where a provenance field is still required.
The compiled transport helper is not included.

The raw **ContractNLI** dataset is **not redistributed** (CC BY 4.0, but behind
a click-through Terms of Use). Sampling metadata, task ids, gold labels and
evidence spans are included; see `README.md` §8 for obtaining the source, with
the expected SHA-256.

`protocol/protocol_lock.json` records the effect of scrubbing honestly: **all 16
task-corpus hashes verify unchanged**; six infrastructure/source files differ
only in docstrings and comments.

## Known reproducibility limitations (unchanged from the study)

- one condition (`gemini-2.5-pro`) was a mutable alias, since withdrawn — it
  cannot be re-verified against the public API
- `results/aborted_qc_run/` is quarantined pre-confirmatory QC data, never used
  in any reported result
- `results/analysis_BUGGY_DISCARDED/` is retained only for auditability and is
  never authoritative

MIT licensed, except ContractNLI-derived content in `corpora/pipeline2/`
(CC BY 4.0, Koreeda & Manning 2021).
