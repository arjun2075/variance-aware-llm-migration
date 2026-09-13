# Baseline / ablation study

Comparison of the proposed variance-aware method against simpler
migration-evaluation strategies, using only existing confirmatory
outputs. No model calls.

## A2 — deterministic-incumbent assumption

Conventional regression logic treats the incumbent as a stable oracle
(`W_A = 1`), giving `Delta_det = C_AB - 1`. The identity
`Delta_det - Delta = -(1 - W_A)` holds for every cell (56/56 verified).

The shift depends only on the property, not the candidate: it is
exactly the incumbent's own instability.

| property | W_A | shift applied by the deterministic assumption |
|---|---|---|
| P1·M1.opportunity_multiset | 0.0000 | -1.0000 |
| P1·M1.opportunity_sequence | 0.0000 | -1.0000 |
| P1·M2.risks | 0.0395 | -0.9605 |
| P1·M2.recommendations | 0.0908 | -0.9092 |
| P1·M2.strengths | 0.1047 | -0.8953 |
| P1·M2.opportunities | 0.1235 | -0.8765 |
| P1·M1.impact | 0.6910 | -0.3090 |
| P1·M3.summary | 0.7352 | -0.2648 |
| P1·M1.collaboration | 0.8314 | -0.1686 |
| P2·extracted_span_set_agreement | 0.8533 | -0.1467 |
| P1·M1.delivery_consistency | 0.8539 | -0.1461 |
| P2·cited_span_set_agreement | 0.8560 | -0.1440 |
| P1·M1.technical_execution | 0.8846 | -0.1154 |
| P2·label_agreement | 0.9286 | -0.0714 |

**Interpretation changes on 0/12 P2 cells** when the deterministic assumption is applied at the declared tolerance.


## A3 — panel / pooled estimator

The pilot's pooled statistic reports one number per property,
averaging over candidates. The spread column shows what that hides.

| property | pooled Delta | min candidate | max candidate | spread |
|---|---|---|---|---|
| P1·M1.collaboration | -0.2278 | -0.3628 | -0.0968 | 0.2659 |
| P1·M1.impact | -0.1948 | -0.3495 | -0.1043 | 0.2452 |
| P2·cited_span_set_agreement | -0.2744 | -0.4031 | -0.2055 | 0.1975 |
| P2·extracted_span_set_agreement | -0.2297 | -0.3217 | -0.1523 | 0.1694 |
| P1·M1.technical_execution | -0.0455 | -0.0996 | +0.0201 | 0.1196 |
| P1·M3.summary | -0.0530 | -0.0962 | -0.0253 | 0.0709 |
| P1·M1.delivery_consistency | -0.1040 | -0.1409 | -0.0707 | 0.0703 |
| P2·label_agreement | -0.1035 | -0.1290 | -0.0648 | 0.0642 |
| P1·M2.recommendations | -0.0407 | -0.0714 | -0.0122 | 0.0592 |
| P1·M2.opportunities | -0.0474 | -0.0640 | -0.0225 | 0.0414 |
| P1·M2.strengths | -0.0558 | -0.0647 | -0.0429 | 0.0218 |
| P1·M2.risks | -0.0255 | -0.0315 | -0.0208 | 0.0108 |
| P1·M1.opportunity_multiset | +0.0000 | +0.0000 | +0.0000 | 0.0000 |
| P1·M1.opportunity_sequence | +0.0000 | +0.0000 | +0.0000 | 0.0000 |

Largest concealment: **P1·M1.collaboration**, where the pooled value -0.2278 spans candidates from -0.3628 to -0.0968 (spread 0.2659).

## A4 — correctness-only evaluation (P2)

What an engineer would conclude from gold correctness alone.

| property | candidate | behavioural Delta | accuracy Delta | correctness signal | quadrant |
|---|---|---|---|---|---|
| label_agreement | gpt-5.4-2026-03-05 | -0.0648 | -0.0387 | indeterminate | indeterminate_correctness_ch |
| cited_span_set_agreeme | gpt-5.4-2026-03-05 | -0.2069 | +0.0656 | indeterminate | indeterminate_correctness_ch |
| label_agreement | gemini-2.5-pro | -0.1236 | -0.1254 | worse | B_behavior_changed_correctne |
| cited_span_set_agreeme | gemini-2.5-pro | -0.2055 | -0.0906 | worse | B_behavior_changed_correctne |
| label_agreement | amazon.nova-pro-v1-0 | -0.0965 | -0.0321 | indeterminate | indeterminate_correctness_ch |
| cited_span_set_agreeme | amazon.nova-pro-v1-0 | -0.2822 | -0.1569 | worse | B_behavior_changed_correctne |
| label_agreement | meta.llama4-maverick-1 | -0.1290 | -0.0887 | worse | B_behavior_changed_correctne |
| cited_span_set_agreeme | meta.llama4-maverick-1 | -0.4031 | -0.2557 | worse | B_behavior_changed_correctne |

**Correctness alone misses substantial behavioural change in 1 cell(s)**: the accuracy CI straddles zero while the behavioural effect exceeds 0.10 in magnitude.

- cited_span_set_agreement / gpt-5.4-2026-03-05: behavioural -0.2069, accuracy +0.0656 CI [-0.052, +0.182]

**Behavioural testing alone would penalise 1 cell(s)** that show no evidence of worse correctness.

- cited_span_set_agreement / gpt-5.4-2026-03-05: behaviourally rejected, accuracy +0.0656 (indeterminate)

## A5 — schema-only evaluation

| model | pipeline | schema valid | verbatim grounding |
|---|---|---|---|
| gpt-5.4-2026-03-05 | P1 | 1.0000 | n/a |
| gemini-2.5-pro | P1 | 0.9933 | n/a |
| amazon.nova-pro-v1-0 | P1 | 0.9633 | n/a |
| meta.llama4-maverick-17b-instr | P1 | 0.9967 | n/a |
| gpt-5.4-2026-03-05 | P2 | 1.0000 | 1.0 |
| gemini-2.5-pro | P2 | 1.0000 | 0.937008 |
| amazon.nova-pro-v1-0 | P2 | 1.0000 | 0.660256 |
| meta.llama4-maverick-17b-instr | P2 | 1.0000 | 0.768002 |

**10 of 12 P2 cells are rejected on behaviour while showing perfect (1.000) schema validity.** Schema validation alone would report no problem in any of them.

