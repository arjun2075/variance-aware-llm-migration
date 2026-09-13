# ContractNLI subset representativeness

- selected (frozen P2 primary): **60** tasks
- eligible pool under the frozen rules: **7191** instances
- eligibility: non-empty document text <= 60,000 chars, gold label in ('Entailment', 'Contradiction', 'NotMentioned')

The 60 frozen tasks were not resampled or modified.

## The label balance is BY DESIGN

The frozen sampler stratifies to **20/20/20** across the three gold
labels. Any difference from ContractNLI's natural label distribution
is an intended property of the design, **not** evidence of a sampling
bug. Those rows are marked `by_design=True` and are excluded from the
question of whether the subset is atypical.

## Categorical variables

| variable | by design | selected | pool | abs. pp difference |
|---|---|---|---|---|
| gold_label=Contradiction | YES | 0.333 | 0.117 | 21.64 pp |
| gold_label=Entailment | YES | 0.333 | 0.491 | 15.76 pp |
| gold_label=NotMentioned | YES | 0.333 | 0.392 | 5.88 pp |
| has_evidence=False | no | 0.333 | 0.392 | 5.88 pp |
| has_evidence=True | no | 0.667 | 0.608 | 5.88 pp |

## Continuous variables

| variable | selected mean | pool mean | selected median | pool median | SMD | reading |
|---|---|---|---|---|---|---|
| n_doc_chars | 10271.7 | 11049.3 | 8890.0 | 9936.0 | -0.117 | small |
| n_evidence_spans | 1.2 | 1.2 | 1.0 | 1.0 | +0.039 | negligible |
| evidence_chars | 314.4 | 296.3 | 288.5 | 226.0 | +0.051 | negligible |

### Quantile comparison

| variable | set | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|
| n_doc_chars | selected | 5084 | 6217 | 8891 | 13416 | 17266 |
| n_doc_chars | pool | 4192 | 6366 | 9936 | 13724 | 20439 |
| n_evidence_spans | selected | 0 | 0 | 1 | 2 | 3 |
| n_evidence_spans | pool | 0 | 0 | 1 | 2 | 3 |
| evidence_chars | selected | 0 | 0 | 291 | 537 | 630 |
| evidence_chars | pool | 0 | 0 | 226 | 447 | 749 |

## Hypothesis coverage

- distinct hypotheses in the subset: **17** of 17 (100.0%)
- most tasks drawn from any single hypothesis: **10**

## Verdict

Aside from the intentional label balancing, no continuous variable differs by more than a *small* standardized difference: n_doc_chars (SMD -0.117).

The subset is not obviously atypical of the eligible workload.
