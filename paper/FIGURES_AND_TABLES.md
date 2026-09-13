# Planned figures and tables

Specified **before results were inspected**, so the presentation cannot be
selected to flatter an outcome. Each entry names its data source in
`results/analysis/` and the claim it supports. `[R-n]` markers are unresolved
placeholders.

---

## Figure 1 — The variance-aware framework

**Type:** conceptual diagram, no data.
**Claim:** a migration test must measure candidate divergence *relative to* the
incumbent's own variation.

Three panels on a shared agreement axis:
(a) `W_A` — incumbent vs. itself, the reference band;
(b) `C_AB` — incumbent vs. candidate;
(c) `Delta = C_AB − W_A` with its interval against a declared tolerance.

Must make visible that a candidate can differ from the incumbent while still
falling inside the incumbent's own variability.

## Figure 2 — Incumbent self-variation vs. incumbent→candidate divergence

**Source:** `pairwise_results.json` (`W_A`, `C_AB` per property per candidate).
**Type:** scatter, `W_A` on x, `C_AB` on y, one point per
(candidate × property), faceted by pipeline. Diagonal `y = x` drawn.
**Claim:** `RESULTS-DEPENDENT`.

The diagonal is the interpretive anchor: on it, the candidate agrees with the
incumbent exactly as much as the incumbent agrees with itself. Below it,
migration adds divergence. Points at low `W_A` mark properties where the
incumbent is barely self-consistent and no migration verdict is meaningful — that
region should be shaded and labelled.

## Figure 3 — Migration compatibility matrix

**Source:** `pairwise_results.json`.
**Type:** heatmap/forest hybrid. Rows = candidate migrations; columns = output
properties; each cell shows `Delta`, its interval, and the tolerance verdict.
Faceted by pipeline.
**Claim:** `RESULTS-DEPENDENT` — whether compatibility is a property of two
model names or varies by property.

Pipeline 1 cells show effect and interval but **no verdict colour**, since no
tolerance is declared there. This asymmetry is deliberate and must be visible in
the legend rather than hidden.

## Figure 4 — Tolerance sensitivity curves

**Source:** `tolerance_curve` fields.
**Type:** small multiples, one per property; x = tolerance (0.01–0.20),
y = verdict as a step function; one line per candidate.
**Claim:** `RESULTS-DEPENDENT` — whether conclusions survive threshold choice.

This figure is the direct successor to the pilot observation that 7 of 11
metrics flipped verdict between margins 0.05 and 0.15. A near-flat family of
curves would mean robust conclusions; steep transitions near the declared
tolerance would mean tolerance-conditional ones. Both are reportable.

## Figure 5 — Correctness × behaviour quadrants (Pipeline 2)

**Source:** correctness decomposition rows.
**Type:** scatter. x = behavioural `Delta`; y = accuracy change
(candidate − incumbent) with interval bars. Four quadrants labelled A–D, with
the vertical zero line and the declared tolerance band drawn.
**Claim:** `RESULTS-DEPENDENT`.

The figure exists to make quadrants **A** and **D** legible:
- **A** (behaviour changed, correctness improved) — a behavioural regression test
  would wrongly block this migration;
- **D** (behaviour preserved, incumbent error preserved) — agreement on being
  wrong, which a behavioural test cannot distinguish from success.

Quadrant D points must be annotated with agreement-on-incumbent-errors.

## Figure 6 — Cross-pipeline comparison

**Source:** both pipelines' pairwise results.
**Type:** paired dot plot; same candidate, same conceptual property class,
Pipeline 1 vs. Pipeline 2.
**Claim:** `RESULTS-DEPENDENT` — whether conclusions generalise beyond one
scaffold, and hence how broadly the secondary claim can be stated.

Only conceptually comparable property classes may be paired; the pipelines'
metrics are not identical and forcing a mapping would be misleading. Pairings
are enumerated explicitly in the caption.

---

## Table 1 — Design and execution summary

**Source:** `execution_summary.json`.

| Row | Value |
|---|---|
| Pipelines | 2 |
| Primary / stress instances per pipeline | 60 / 20 |
| Conditions (incumbent + candidates) | 1 + 4 |
| Repetitions (incumbent / candidate) | 8 / 5 |
| Planned runs / calls | 5,040 / 20,160 |
| Accepted runs | [R-1] |
| Excluded runs, by reason | [R-2] |
| Total input / output tokens | [R-3] |
| Wall-clock | [R-4] |
| Canonical provenance mismatches | [R-5] |

## Table 2 — Primary pairwise migration results

Rows: pipeline × candidate × property. Columns: `W_A`, `C_AB`, `Delta`, 95%
interval, eligible within/cross pairs, declared tolerance, verdict.

Pipeline 1 rows carry "no declared tolerance" in the verdict column — not a
blank, which would read as an omission.

## Table 3 — Correctness × behaviour decomposition (Pipeline 2)

Rows: candidate × property. Columns: behavioural `Delta`, behaviour preserved,
incumbent accuracy, candidate accuracy, accuracy change with interval, quadrant,
success, agreement-on-incumbent-errors, n incumbent errors.

**Behavioural preservation is never shown without the paired correctness change**
— the table is constructed so the two cannot be read apart.

## Table 4 — Schema and invariant compliance

Rows: condition. Columns: schema-valid rate, parse-success rate, label-in-set
rate, verbatim-grounding rate, truncation rate.

Scoped explicitly to this scaffold's prompt-only structured output; **not** a
claim about any provider's structured-output capability. The Amendment 001
ceiling is stated in the caption, since compliance is sensitive to it.

## Table 5 — Operational profile

Rows: condition. Columns: median/mean/p90 per-call latency, input and output
tokens per run, retry rate, estimated cost.

Latency is reported from the synchronous operational subset only. Serial pacing
intervals are stated in the caption so latency is not misread as achievable
throughput.

## Table 6 — Semantic-matching sensitivity

Rows: property × candidate. Columns: `Delta` at cosine thresholds
{0.70, 0.75, 0.80, 0.85, 0.90} and the threshold-free aggregate; a flag for any
verdict change across the sweep.

## Table 7 — Stress-set results

Same shape as Table 2, on the 20 pre-frozen stress instances per pipeline.
Reported **separately and never pooled** with the primary set. Caption states
that the stress sets were frozen in advance and were not added in response to
any primary result.

## Table 8 — Direct-provider replication

Rows: condition × property. Columns: confirmatory `Delta`, replication `Delta`,
agreement in direction and verdict.

The mutable-alias condition is marked so that its divergence is not read as a
serving-path effect. Per-condition faithfulness (exact identifier / unverified /
mutable alias) appears as its own column, not a footnote.

---

## Placeholder register

| Marker | Meaning | Source |
|---|---|---|
| `[R-1]` | accepted runs | `execution_summary.json` |
| `[R-2]` | exclusions by reason | `execution_summary.json` |
| `[R-3]` | total tokens | ledger aggregate |
| `[R-4]` | wall-clock | ledger timestamps |
| `[R-5]` | provenance mismatches | `execution_summary.json` |

No placeholder is resolved until the frozen analysis has run on the complete
grid.
