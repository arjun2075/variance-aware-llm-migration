# EXECUTION_REPORT.md

**Study:** Variance-Aware Regression Testing for Model Migration in Compound LLM Pipelines
**Confirmatory grid executed:** 2026-09-09 → 2026-09-12
**Status: COMPLETE**

## 1. Counts — verified

| | Planned | Actual |
|---|---|---|
| Calls | 20,160 | **20,160** ✅ |
| Runs | 5,040 | **5,040** ✅ |
| Runs with all 4 stages | 5,040 | **5,040** ✅ |
| Accepted runs | — | **5,040 (100%)** |
| Excluded runs | — | **0** |

Per partition, all at planned size:

| Pipeline / partition | Runs |
|---|---|
| P1 primary | 1,680 |
| P1 stress | 560 |
| P1 sync operational | 280 |
| P2 primary | 1,680 |
| P2 stress | 560 |
| P2 sync operational | 280 |

Runs per condition: incumbent 1,440 (8 reps × 180 tasks), each candidate 900
(5 reps × 180 tasks).

## 2. Provenance — verified

**0 canonical model mismatches across all 20,160 calls.**

| Requested | Returned canonical | Runs |
|---|---|---|
| gpt-4o-2024-11-20 | gpt-4o-2024-11-20 | 1,440 |
| gpt-5.4-2026-03-05 | gpt-5.4-2026-03-05 | 900 |
| gemini-2.5-pro | gemini-2.5-pro | 900 |
| amazon.nova-pro-v1-0 | us.amazon.nova-pro-v1:0 | 900 |
| meta.llama4-maverick-17b-instruct-v1-0 | us.meta.llama4-maverick-17b-instruct-v1:0 | 900 |

Three of five identifiers are rewritten by the managed execution path; each matched the
frozen map established by live probe before execution.

## 3. Hash verification

**All 16 corpus and prompt files byte-identical to the freeze.**

| Artifact | SHA-256 (first 16) | Status |
|---|---|---|
| P1 primary corpus | `6215f2a99e5455bf` | unchanged |
| P1 stress corpus | `bc6e5539d40acb25` | unchanged |
| P2 primary corpus | `53082a01241d2488` | unchanged |
| P2 stress corpus | `f96006eebec93ca1` | unchanged |
| All 8 prompt templates | — | unchanged |

Protocol verification reports three changed **code** files — `shim.py`,
`run_experiment.py`, and a `.pyc` — corresponding to the documented
auth-recovery fix (commit `e30c78e`) applied mid-run after a host restart.
No other drift.

## 4. Errors, retries, exclusions

**Final ledger: 0 errors.**

| | Count |
|---|---|
| Retries | 20 (0.10% of calls) |
| Truncations (`finish_reason=length`) | **0** |
| Parse failures | 53 (0.26% of calls) |
| Schema violations | 29 runs (0.6%) |
| Schema-valid runs | 5,011 / 5,040 (99.4%) |

Parse failures and schema violations are **data, not exclusions**, per the
frozen acceptance rules; they are reported as compliance metrics.

### Transient infrastructure failures, re-executed

Three separate `the credential helper` ticket-fetch incidents occurred, each self-recovering
within ~1 minute. In every case the affected runs were purged and re-executed
rather than excluded, because the frozen rule excludes a run on transport
failure *after* the retry budget is exhausted — these calls never reached a
model. Total affected: **17 runs of 5,040 (0.3%)**, all completed on re-execution.
Audit trail with backups and hashes: `results/run/AUTH_PURGE_AUDIT.json`
(3 events).

One further incident: a host restart left the long-lived transport helper process alive but
with stale auth state, causing every model to return 403 for ~85 seconds. This
was diagnosed, fixed with an auth-recovery path, and the 12 affected runs
re-executed. See §7.

## 5. Token usage and duration

| | Value |
|---|---|
| Input tokens | **20,674,205** |
| Output tokens | **12,131,327** |
| Total | 32,805,532 |
| Wall-clock span | 70.9 h |
| Mean rate | 0.085 calls/s |

## 6. Operational latency (all calls)

| Model | Median (s) | Mean (s) | p90 (s) |
|---|---|---|---|
| gemini-2.5-pro | **18.46** | 19.30 | 29.70 |
| gpt-5.4-2026-03-05 | 4.53 | 5.19 | 8.69 |
| gpt-4o-2024-11-20 | 3.86 | 4.62 | 7.52 |
| us.amazon.nova-pro-v1:0 | 3.12 | 3.24 | 4.46 |
| us.meta.llama4-maverick-17b-instruct-v1:0 | 2.67 | 2.90 | 4.02 |

Gemini is ~5× slower than the incumbent per call, consistent with its heavy
use of internal reasoning tokens (see Amendment 001).

**Execution was strictly serial** (no concurrency permitted by the managed execution path) with
minimum inter-call intervals of 2 s general and 15 s for Bedrock-backed
families. Of the 70.9 h span, roughly 27 h was model time, ~16 h was the
Bedrock pacing floor, and ~5 h was host downtime. **Zero 429 responses were
observed in 20,160 calls, including 5,054 Bedrock calls** — the intervals were
conservative defaults, not measured limits, and a replicator need not inherit
them.

## 7. Amendments and incidents

### Amendment 001 — output ceiling 2,048 → 8,192
An initial 82-call QC run showed `gemini-2.5-pro` truncating on 15/28 calls
(54%) while no other condition truncated once. The ceiling was raised
**uniformly** for all five conditions; per-model ceilings were rejected as they
would make the serving configuration non-uniform. The QC run was quarantined
(`results/aborted_qc_run/`, ledger SHA-256 `01c641f8…`) and excluded from all
analysis; the experiment restarted from zero. Post-amendment QC: truncation
15/28 → 0/7, others 0, all outputs parseable, all provenance correct.

**Final confirmatory grid: 0 truncations in 20,160 calls.**

### Incident — post-suspend auth failure
A host restart left the transport helper process alive with stale auth state; all five
models returned 403 within 85 s. Diagnosed by elimination (a fresh process
authenticated fine). Fixed by adding a transport helper-restart path on 401/403 that
re-fetches the IAM ticket and retries **under the same frozen retry budget**.
12 affected runs re-executed.

### Completion check — 3 stranded runs recovered
The runner initially stopped at 20,151 calls. Investigation found three runs
stranded at stage 1: earlier purges had removed a failed call while a stage-1
sibling survived, so resume skipped them as "already recorded". The orphan
calls were cleared and the runs re-executed in full. **Without this check three
runs would have been silently excluded.**

## 8. Analysis integrity — a bug found and fixed

The first analysis pass reported `W_A = 1.000` for P2 label agreement. This was
checked against the raw data and found impossible: the incumbent returns
different labels across its 8 repetitions on **10 of 60 tasks**.

Root cause in `build_matrices`: the within-model branch used
`pair_value(...) or np.nan`. A disagreement scores `0.0`, which is falsy, so
every disagreement was silently converted to an ineligible pair. Only
agreements reached `W_A`, biasing it toward 1.0 and making **every delta
systematically too negative**. The cross-model branch used an explicit `None`
check and was unaffected.

Fixed with an explicit `None` check and two regression tests. The buggy output
is quarantined at `results/analysis_BUGGY_DISCARDED/` and is used for nothing.
All reported results come from the corrected re-run.

## 9. Verdict

The confirmatory grid executed **completely and cleanly**: every planned call
made, every run complete, zero exclusions, zero provenance mismatches, zero
truncations, and all corpus and prompt hashes unchanged from the freeze.
