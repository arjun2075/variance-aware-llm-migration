# Single-run regression-oracle instability

Conventional regression testing captures one incumbent execution as
the expected output. This enumerates all 8 possible choices exactly.

- cells analysed: **56**
- oracle choices per cell: **8** (exact enumeration, not sampling)
- mean agreement range across oracle choices: **0.0342**
- largest range: **0.0884** (P1·M1.impact / meta.llama4-maverick-17b)

## Identity check

The mean over uniformly-chosen single oracles must equal the
all-repetition cross-agreement. Maximum residual across all cells: **7.98e-04**.

## Verdict instability (P2, declared tolerance 0.05)

**1 of 12 P2 cells** yield more than one verdict
depending only on which incumbent run was chosen as the oracle.

| property | candidate | delta range | verdicts |
|---|---|---|---|
| label_agreement | gpt-5.4-2026-03-05 | [-0.0886, -0.0386] | {"within_tolerance": 0.375, "worse_than_tolerance": 0.625} |

## All cells

| pipeline | property | candidate | oracle mean | min | max | range | sd |
|---|---|---|---|---|---|---|---|
| P1 | M1.impact | meta.llama4-maverick-1 | 0.5589 | 0.5162 | 0.6047 | 0.0884 | 0.0317 |
| P1 | M1.delivery_consistency | gpt-5.4-2026-03-05 | 0.7129 | 0.6817 | 0.7650 | 0.0833 | 0.0291 |
| P1 | M1.collaboration | gpt-5.4-2026-03-05 | 0.4687 | 0.4400 | 0.5183 | 0.0783 | 0.0254 |
| P1 | M1.impact | amazon.nova-pro-v1-0 | 0.4979 | 0.4550 | 0.5283 | 0.0733 | 0.0255 |
| P1 | M1.collaboration | gemini-2.5-pro | 0.7355 | 0.7033 | 0.7750 | 0.0717 | 0.0225 |
| P2 | cited_span_set_agreement | gemini-2.5-pro | 0.6504 | 0.6183 | 0.6859 | 0.0677 | 0.0231 |
| P2 | extracted_span_set_agree | gpt-5.4-2026-03-05 | 0.6285 | 0.5933 | 0.6583 | 0.0649 | 0.0202 |
| P1 | M1.impact | gemini-2.5-pro | 0.3404 | 0.3050 | 0.3695 | 0.0645 | 0.0221 |
| P2 | extracted_span_set_agree | gemini-2.5-pro | 0.6330 | 0.5991 | 0.6633 | 0.0642 | 0.0245 |
| P1 | M1.impact | gpt-5.4-2026-03-05 | 0.5867 | 0.5533 | 0.6167 | 0.0633 | 0.0233 |
| P2 | extracted_span_set_agree | amazon.nova-pro-v1-0 | 0.7010 | 0.6788 | 0.7375 | 0.0587 | 0.0234 |
| P2 | cited_span_set_agreement | amazon.nova-pro-v1-0 | 0.5738 | 0.5511 | 0.6094 | 0.0583 | 0.0230 |
| P1 | M1.delivery_consistency | amazon.nova-pro-v1-0 | 0.7499 | 0.7350 | 0.7917 | 0.0567 | 0.0213 |
| P2 | cited_span_set_agreement | gpt-5.4-2026-03-05 | 0.6491 | 0.6116 | 0.6676 | 0.0561 | 0.0197 |
| P2 | label_agreement | gpt-5.4-2026-03-05 | 0.8638 | 0.8400 | 0.8900 | 0.0500 | 0.0199 |
| P2 | extracted_span_set_agree | meta.llama4-maverick-1 | 0.5317 | 0.5069 | 0.5568 | 0.0499 | 0.0168 |
| P1 | M1.delivery_consistency | meta.llama4-maverick-1 | 0.7530 | 0.7325 | 0.7792 | 0.0467 | 0.0173 |
| P1 | M1.collaboration | meta.llama4-maverick-1 | 0.6896 | 0.6654 | 0.7110 | 0.0456 | 0.0143 |
| P1 | M1.collaboration | amazon.nova-pro-v1-0 | 0.5178 | 0.4983 | 0.5413 | 0.0429 | 0.0171 |
| P1 | M2.opportunities | meta.llama4-maverick-1 | 0.0805 | 0.0603 | 0.1014 | 0.0411 | 0.0131 |
| P2 | label_agreement | gemini-2.5-pro | 0.8050 | 0.7833 | 0.8233 | 0.0400 | 0.0140 |
| P2 | label_agreement | meta.llama4-maverick-1 | 0.7996 | 0.7800 | 0.8200 | 0.0400 | 0.0146 |
| P1 | M1.technical_execution | meta.llama4-maverick-1 | 0.9050 | 0.8867 | 0.9233 | 0.0367 | 0.0131 |
| P1 | M1.delivery_consistency | gemini-2.5-pro | 0.7835 | 0.7679 | 0.8029 | 0.0350 | 0.0128 |
| P1 | M2.risks | gemini-2.5-pro | 0.0175 | 0.0050 | 0.0394 | 0.0344 | 0.0107 |
| P1 | M2.strengths | meta.llama4-maverick-1 | 0.0449 | 0.0281 | 0.0606 | 0.0325 | 0.0112 |
| P1 | M1.technical_execution | gpt-5.4-2026-03-05 | 0.8801 | 0.8712 | 0.9033 | 0.0321 | 0.0135 |
| P2 | cited_span_set_agreement | meta.llama4-maverick-1 | 0.4529 | 0.4413 | 0.4733 | 0.0320 | 0.0134 |
| P1 | M1.technical_execution | gemini-2.5-pro | 0.7853 | 0.7662 | 0.7979 | 0.0316 | 0.0109 |
| P2 | label_agreement | amazon.nova-pro-v1-0 | 0.8321 | 0.8200 | 0.8500 | 0.0300 | 0.0099 |
| P1 | M2.recommendations | amazon.nova-pro-v1-0 | 0.0786 | 0.0665 | 0.0953 | 0.0288 | 0.0093 |
| P1 | M1.technical_execution | amazon.nova-pro-v1-0 | 0.7864 | 0.7733 | 0.8000 | 0.0267 | 0.0085 |
| P1 | M2.opportunities | amazon.nova-pro-v1-0 | 0.1009 | 0.0864 | 0.1131 | 0.0267 | 0.0096 |
| P1 | M2.risks | amazon.nova-pro-v1-0 | 0.0187 | 0.0094 | 0.0339 | 0.0244 | 0.0093 |
| P1 | M2.strengths | gemini-2.5-pro | 0.0487 | 0.0349 | 0.0578 | 0.0229 | 0.0075 |
| P1 | M2.opportunities | gemini-2.5-pro | 0.0631 | 0.0523 | 0.0746 | 0.0223 | 0.0081 |
| P1 | M3.summary | gpt-5.4-2026-03-05 | 0.6980 | 0.6876 | 0.7085 | 0.0209 | 0.0066 |
| P1 | M2.recommendations | gemini-2.5-pro | 0.0501 | 0.0425 | 0.0624 | 0.0199 | 0.0071 |
| P1 | M2.strengths | amazon.nova-pro-v1-0 | 0.0618 | 0.0532 | 0.0727 | 0.0195 | 0.0071 |
| P1 | M3.summary | gemini-2.5-pro | 0.6818 | 0.6719 | 0.6911 | 0.0191 | 0.0059 |
| P1 | M2.opportunities | gpt-5.4-2026-03-05 | 0.0595 | 0.0505 | 0.0692 | 0.0188 | 0.0075 |
| P1 | M2.risks | meta.llama4-maverick-1 | 0.0080 | 0.0000 | 0.0186 | 0.0186 | 0.0052 |
| P1 | M2.strengths | gpt-5.4-2026-03-05 | 0.0400 | 0.0315 | 0.0499 | 0.0184 | 0.0066 |
| P1 | M3.summary | amazon.nova-pro-v1-0 | 0.7099 | 0.7017 | 0.7147 | 0.0130 | 0.0038 |
| P1 | M2.risks | gpt-5.4-2026-03-05 | 0.0118 | 0.0069 | 0.0192 | 0.0122 | 0.0045 |
| P1 | M3.summary | meta.llama4-maverick-1 | 0.6389 | 0.6332 | 0.6454 | 0.0122 | 0.0039 |
| P1 | M2.recommendations | meta.llama4-maverick-1 | 0.0194 | 0.0146 | 0.0256 | 0.0110 | 0.0047 |
| P1 | M2.recommendations | gpt-5.4-2026-03-05 | 0.0523 | 0.0498 | 0.0571 | 0.0072 | 0.0025 |
| P1 | M1.opportunity_multiset | gpt-5.4-2026-03-05 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_sequence | gpt-5.4-2026-03-05 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_multiset | gemini-2.5-pro | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_sequence | gemini-2.5-pro | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_multiset | amazon.nova-pro-v1-0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_sequence | amazon.nova-pro-v1-0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_multiset | meta.llama4-maverick-1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| P1 | M1.opportunity_sequence | meta.llama4-maverick-1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
