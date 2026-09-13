# REPLICATION_REPORT.md

**Direct-provider replication of the frozen subset.**
Executed 2026-09-12, after the confirmatory grid completed and after the
primary analyses were written.

| | |
|---|---|
| Subset | 10 P1 + 10 P2 tasks, frozen 2026-09-11 **before any result was inspected**, hash `ebaba1cb…` |
| Repetitions | incumbent 8, candidate 5 — unchanged |
| Prompts, corpora, metrics, tolerance, semantic threshold | unchanged |
| Calls | **1,040 / 1,040**, 260 runs, all four stages, **0 errors** |
| Transport | OpenAI public API, direct |

The subset was **not modified** in light of the primary results. Nothing frozen
was changed.

---

## 1. Coverage — 2 of 5 conditions, for three distinct reasons

| Condition | Replicated? | Reason |
|---|---|---|
| `gpt-4o-2024-11-20` (incumbent) | ✅ yes | immutable id, direct OpenAI API |
| `gpt-5.4-2026-03-05` | ✅ yes | immutable id, direct OpenAI API |
| `gemini-2.5-pro` | ❌ **not evaluable** | withdrawn from new users by the provider |
| `amazon.nova-pro-v1:0` | ❌ **not evaluable** | no direct Bedrock access exists |
| `meta.llama4-maverick-17b-instruct-v1:0` | ❌ **not evaluable** | no direct Bedrock access exists |

The two replicated conditions are the ones that matter most: without the
incumbent there is no `W_A` and therefore no `Delta` at all, and the pair gives
a **fully attributable** same-provider migration comparison, since both
identifiers are immutable dated snapshots on both paths.

### The Gemini gap is itself a finding

`gemini-2.5-pro` appears in the provider's model listing with `generateContent`
among its supported methods, but every call returns HTTP 404:

> This model models/gemini-2.5-pro is no longer available to new users.
> Please update your code to use models/gemini-3.1-pro-preview

`gemini-3.1-pro-preview` was **not** substituted. It is a different model, and
running it while claiming to replicate the `gemini-2.5-pro` condition would
compare two models under the guise of comparing serving paths.

The consequence is worth stating plainly in the paper: **a mutable model
identifier became unverifiable within three days of the experiment that used
it.** The confirmatory measurement for that condition stands — it was made,
logged and provenance-checked — but it can no longer be re-verified against the
public API by anyone, including us. This is the reproducibility hazard the study
warns about, realised on the study itself.

The two Bedrock gaps are different in kind: a scope limitation, not a
provider withdrawal. The research was designed around managed execution path access, and no
personal Bedrock account exists to reach those models directly.

## 2. Result — every evaluable property replicates

14 properties evaluable (11 P1, 3 P2), all on the same 20 frozen tasks and the
same two conditions.

| | Count |
|---|---|
| Same sign of `Delta` | **14 / 14** |
| Confidence intervals overlap | **14 / 14** |
| Same verdict | **14 / 14** |

| Pipeline | Property | managed execution path `Delta` | Direct `Delta` | Difference |
|---|---|---|---|---|
| P1 | M1.technical_execution | −0.045 | −0.041 | +0.004 |
| P1 | M1.delivery_consistency | −0.145 | −0.155 | −0.010 |
| P1 | M1.collaboration | −0.255 | −0.342 | **−0.088** |
| P1 | M1.impact | −0.045 | −0.249 | **−0.204** |
| P1 | M1.opportunity_multiset | 0.000 | 0.000 | 0.000 |
| P1 | M1.opportunity_sequence | 0.000 | 0.000 | 0.000 |
| P1 | M2.strengths | −0.085 | −0.103 | −0.017 |
| P1 | M2.opportunities | −0.049 | −0.061 | −0.012 |
| P1 | M2.risks | −0.032 | −0.051 | −0.018 |
| P1 | M2.recommendations | −0.022 | −0.050 | −0.028 |
| P1 | M3.summary | −0.028 | −0.061 | −0.033 |
| P2 | label_agreement | +0.029 | +0.030 | +0.002 |
| P2 | cited_span_set_agreement | −0.137 | −0.119 | +0.018 |
| P2 | extracted_span_set_agreement | −0.165 | −0.141 | +0.024 |

Twelve of fourteen differences are under 0.05. Two exceed it:

- **M1.impact** (−0.045 → −0.249, difference −0.204) — the largest divergence in
  the comparison. On 10 tasks the confidence intervals still overlap, so this is
  not a demonstrated serving-path effect, but it is the one cell where the two
  paths disagree enough to warrant explicit mention rather than being folded
  into a "replicates" summary.
- **M1.collaboration** (−0.255 → −0.342, difference −0.088).

Both are P1 properties with no declared tolerance, so neither carries a verdict
either way. Both sit on a 10-task subset whose intervals are roughly 2.5× wider
than the 60-task primary set.

**Incumbent self-agreement is stable across paths**, which is the precondition
for any of this to be interpretable: `W_A` moves by ≤0.012 on six of seven
representative properties (e.g. technical_execution 0.884 → 0.886, label
0.921 → 0.932, cited spans 0.851 → 0.839). The exception is M1.impact
(0.700 → 0.786), which is also the cell with the largest `Delta` difference —
consistent with that property simply being noisier on this subset.

## 3. Which primary conclusions replicated

### Replicated

1. **The incumbent does not agree with itself, and `W_A` is property-dependent.**
   Reproduced on the direct path with near-identical values.
2. **Migration deltas are negative on essentially every behavioural property.**
   14/14 same sign.
3. **Evidence selection destabilises more than the final label.** On the direct
   path, P2 span deltas (−0.119, −0.141) remain far larger in magnitude than the
   label delta (+0.030) — the same asymmetry, on the same 10 tasks.
4. **Exact-match metrics on free text are degenerate.** `Delta = 0.000` on both
   paths for multiset and sequence agreement, because `W_A = C_AB = 0`.
5. **Serving path is not a major confound** for the two immutable-identifier
   conditions. No verdict changes; no CI disjoint.

### Strengthened

6. **The same-provider GPT-4o → GPT-5.4 migration is genuinely mild on labels
   but not on evidence.** the managed execution path's label delta for this pair on the full
   60-task set was −0.065 (inconclusive); on the 10-task subset it is +0.029
   managed execution path / +0.030 direct — positive, i.e. the candidate agrees with the
   incumbent slightly *more* than the incumbent agrees with itself. Meanwhile
   both paths show substantial span divergence. Two independent serving paths
   agreeing on this asymmetry strengthens it.

### Weakened

7. **Nothing was weakened by contradiction**, but two P1 cells (M1.impact,
   M1.collaboration) show larger path-to-path variation than the rest. Neither
   carries a verdict, and both intervals overlap, so no primary conclusion
   depends on them — but claims about *specific P1 effect magnitudes* should be
   stated with the subset-level variation acknowledged.

### Could not be evaluated

8. **Three of five conditions.** `gemini-2.5-pro` (provider withdrawal —
   permanent), `amazon.nova-pro-v1:0` and `meta.llama4-maverick` (no direct
   Bedrock access — scope).
9. **Correctness replication.** The comparison covers behavioural agreement
   only; gold-label and gold-span correctness on the direct path were not part
   of the frozen replication specification and were not computed.
10. **Cross-provider serving-path effects.** Both replicated conditions are
    OpenAI, so the replication says nothing about whether managed execution path-vs-direct
    differences would appear for other providers.

## 4. Operational note

The direct path ran at 0.29 calls/s against the managed execution path's 0.085 — roughly 3.5×
faster, because no serial pacing was imposed.

It also produced **six HTTP 429 rate-limit errors** (account limit: 30,000 TPM
on gpt-4o), which the managed execution path run never encountered in 20,160 calls. The
replication runner initially had no retry path — an omission — so a 429 retry
with exponential backoff was added, matching the frozen 3-attempt budget, and
the six affected runs were purged and re-executed. Final ledger: 1,040 calls,
0 errors.

The irony is worth recording: the managed execution path pacing criticised as over-conservative
in the execution report did prevent exactly this failure mode.

## 5. Scope

This is a **robustness check, not a second confirmatory study**. It uses 20 of
180 tasks and 2 of 5 conditions. It cannot overturn the primary results, and a
"replicates" verdict here means the qualitative conclusions survived a change of
serving path for the conditions it could test — nothing broader.
