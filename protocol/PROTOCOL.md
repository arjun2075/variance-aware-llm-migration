# PROTOCOL — Variance-Aware Regression Testing for Model Migration in Compound LLM Pipelines

**Protocol ID:** `variance-aware-migration-v2-personal`
**Status:** DRAFT — pending freeze. No paid call has been made.
**Machine-readable companion:** `protocol_spec.json` (authoritative for values)
**Freeze tool:** `freeze_protocol.py` → `protocol_lock.json`

Independent personal research project on public vendor APIs. This document
records the pre-registered design; once frozen, any change is detectable via the
protocol hash and anything added later is exploratory by definition.

---

## 1. Framing

**Primary claim.** A model migration should be treated as a *stochastic
regression-testing problem*: candidate behavior is evaluated relative to the
incumbent's own output variability, separately for each pipeline property and
application tolerance.

**Secondary claim.** Migration compatibility is not a single property of two
model names; it varies across pipeline, workload, output property, serving
configuration, and tolerance. *Asserted only as far as two pipelines support.*

**Terminology.** *behavioral preservation*, *migration compatibility*,
*variance-aware regression testing*, *property-specific equivalence*.
**Prohibited:** "safe model swap", "models are (not) substitutable".

## 2. Locked parameters

| Parameter | Value |
|---|---|
| Primary tasks / pipeline | 60 |
| Stress tasks / pipeline | 20 (pre-frozen, separate, **never a rescue**) |
| Incumbent repetitions | 8 |
| Candidate repetitions | 5 |
| Candidates | 4 |
| Primary estimand | `Delta(A→B) = C_AB − W_A` |
| Panel average | secondary/descriptive only |
| Within-model treatment | distinct-repetition off-diagonal (**mandatory**) |
| Execution order | randomized/interleaved; model-major prohibited |
| Bootstrap | two-level cluster, 10,000 replicates, seed 20260803 |

Counts are simulation-derived (`docs/study0/`), not assumed. **The primary task
set is never expanded after observing results.**

## 3. Pipelines

**P1 — compound assessment.** `pr_signal` → `review_signal` → `synthesis` →
`deepen`. Newly authored research-only prompts, released in full. 60 synthetic
cases, genuinely heterogeneous in ambiguity and difficulty, no company data, no
production identifiers, finalized before execution. **No correctness criterion —
behavioral preservation only.** This is a stated limitation.

**P2 — ContractNLI.** `extract_evidence` → `assess_evidence` → `classify` →
`verify`. CC BY 4.0. 60 primary + 20 stress cases frozen with gold labels and
gold evidence spans preserved for scoring.

⚠ **Gold labels and gold evidence spans are never revealed to the model during
inference.** They are used only for post-hoc scoring.

⚠ Sample at the **document** level — the 17 shared hypotheses would otherwise
violate cluster independence.

## 4. P2 metrics — six separated axes

1. incumbent self-variation (`W_A`)
2. incumbent→candidate behavioral agreement (`Delta`)
3. gold-label correctness
4. evidence-span correctness
5. schema/invariant compliance (incl. **verbatim span grounding** — deterministic, no annotation needed)
6. operational behavior

### 4.1 The four outcomes — mandatory joint reporting

| | correctness improved | correctness worsened |
|---|---|---|
| **behavior changed** | **A** — candidate better; a naive oracle wrongly fails it | **B** — genuine regression |
| **behavior preserved** | **C** — clean low-risk migration | **D** — incumbent error preserved |

**D is not a successful migration merely because outputs agree.** Enforced in
code: `MigrationOutcome.is_success` excludes D, and behavioral preservation is
never emitted for P2 without the paired correctness change.

**Pre-registered:** the subset of instances the incumbent gets wrong.
Behavioral agreement on that subset is *agreement-on-errors* — the quantitative
signature of D — and is reported separately.

## 5. Tolerances

**P1: no universal primary equivalence threshold is declared.** No
application-grounded tolerance exists for P1 behavioral agreement, so P1 reports
tolerance/effect curves and issues **no headline verdict**. This is deliberate.

**P2: declared in advance where defensible** — label accuracy 0.05, verbatim
span grounding 0.01, schema validity 0.05.

Sensitivity sweep 0.01–0.20. **Correctness and behavioral equivalence remain
separate concepts throughout** and are never combined into one score.

## 6. Execution

**Batch-first** for the main behavioral/correctness grid, where the exact model
supports batch, the batch path exposes the required request semantics, and batch
does not invalidate the metric. Discounted batch pricing used where offered.

**Dependency waves** — pipelines are sequential, so all stage-1 calls are
batched across tasks × models × repetitions, then stage 2 is built from stage-1
outputs, and so on. Exact task/model/repetition IDs are preserved across every
request and response; rejoins are **by `custom_id`, never by position**.

**Three partitions, all pre-specified before results are seen:**

| Partition | Mode | Purpose |
|---|---|---|
| main grid | batch | behavioral + correctness |
| sync operational subset | sync | per-call & end-to-end latency, retries, timeouts, tokens, parse/schema |
| batch-vs-sync validation | both | detect a major serving-mode effect (not exact equality) |

⚠ **Batch wall-clock is not interactive latency** — enforced in code (batch
results carry `latency_ms = None`). **Execution modes are never switched
silently mid-experiment.**

## 7. Model matrix

Selected on **current public API availability and reproducibility**. Exact dated
snapshots preferred over mutable aliases; where a model cannot be pinned, that
limitation is recorded rather than glossed.

- **Incumbent (preferred):** `gpt-4o-2024-11-20`, the public OpenAI snapshot.
- **Candidates:** a same-provider OpenAI successor; a strong Anthropic model;
  `amazon.nova-pro-v1:0`; `meta.llama4-maverick-17b-instruct-v1:0` or a
  comparable documented public open-weight model.

**Incumbent resolution rule.** Retain if the exact public snapshot is still
callable at freeze. If unavailable, **select and freeze a new incumbent before
execution**; **never silently map** an unavailable GPT-4o identifier to another
model or version; and if the incumbent changes, Study 0 becomes historical pilot
evidence rather than direct continuity, stated in the manuscript.

Selection date and documentation URLs are recorded in
`availability_manifest.json`.

## 8. Study 0

The recovered 8-profile / 5-model / 200-run experiment is a **reproduced
historical pilot**. Its results are never merged into or pooled with this study,
and its internal execution environment is not used here. Permitted uses:
motivation, the budget simulations in `docs/study0/`, and design comparison.

## 9. Proprietary separation

This repository contains no internal production prompt, code, managed execution path, URL,
identifier, credential, or configuration, and has **no dependency** on any.
Enforced by `tests/test_no_proprietary_content.py`, which fails on any internal
identifier, proprietary prompt wording, or credential-shaped string.

## 10. Pricing

**Documentation, not an approval gate.** A pricing manifest is built immediately
before execution recording, per model: provider, exact model id, standard input
and output prices, batch prices where applicable, source URL, and retrieval
date. Actual input/output token usage is recorded for every request; afterwards
both the estimate from frozen prices and actual account spend are reported.

## 11. Freeze checklist

Frozen and hashed before the first paid confirmatory call:

- [ ] repository commit
- [ ] 60 + 20 task corpora for each pipeline
- [ ] public research prompts
- [ ] model IDs
- [ ] serving modes
- [ ] repetition counts
- [ ] primary estimands
- [ ] metrics
- [ ] correctness definitions
- [ ] tolerance analyses
- [ ] execution order / random seed
- [ ] exclusion & retry rules
- [ ] synchronous operational subset
- [ ] batch-vs-sync validation subset

```bash
python protocol/freeze_protocol.py freeze \
  --protocol protocol/PROTOCOL.md --spec protocol/protocol_spec.json \
  --corpus corpora --corpus prompts --code src --out protocol/protocol_lock.json
python protocol/freeze_protocol.py verify --lock protocol/protocol_lock.json
```

Then run the **zero-cost dry run** (`scripts/dry_run.py`). Paid execution begins
only after the freeze verifies and the dry run passes.
