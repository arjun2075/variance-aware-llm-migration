# Invalid-output sensitivity (P2 primary)

Three treatments of invalid / unparseable outputs, applied to the 12
P2 primary cells. Validity is judged PER PROPERTY from the existing
parse and schema flags; no new criterion is introduced.

| policy | treatment of a pair involving an invalid output |
|---|---|
| A frozen | ineligible — excluded from W_A and C_AB (current behaviour) |
| B conservative | scored agreement **0** |
| C complete case | excluded, per property only |

## Policy A reproduces the frozen results: **True**

## Observed invalid-output rate

The highest per-cell invalid fraction is **0.001282** (extracted_span_set_agreement / gemini-2.5-pro).

P2 primary contains **0 schema-invalid runs** and **1 parse failure**
across 1,680 runs. The sensitivity analysis is therefore operating on
an almost-empty perturbation set, and near-identical results across
policies reflect that the failure rate is genuinely near zero — not
that the policies are equivalent in general.

## Headline questions

1. **Does any sign change?** No (0/36 cells)
2. **Does any verdict change?** No (0/36 cells)

3. **Does the span-vs-label asymmetry change?**

| policy | mean \|Delta\| spans | mean \|Delta\| labels | ratio |
|---|---|---|---|
| A_frozen | 0.2521 | 0.1035 | 2.44x |
| B_conservative_failure | 0.2521 | 0.1035 | 2.44x |
| C_complete_case | 0.2518 | 0.1035 | 2.43x |

4. **Does any correctness x behaviour interpretation change?**
   The quadrant assignment depends on the behavioural verdict and the
   accuracy CI. With no verdict changes above, no quadrant changes.

## All results

| property | candidate | policy | W_A | C_AB | Delta | CI | verdict |
|---|---|---|---|---|---|---|---|
| label_agreement | gpt-5.4-2026-03-05 | A_frozen | 0.9286 | 0.8638 | -0.0648 | [-0.136, -0.003] | inconclusive |
| label_agreement | gpt-5.4-2026-03-05 | B_conservative_failure | 0.9286 | 0.8638 | -0.0648 | [-0.136, -0.003] | inconclusive |
| label_agreement | gpt-5.4-2026-03-05 | C_complete_case | 0.9286 | 0.8638 | -0.0648 | [-0.136, -0.003] | inconclusive |
| cited_span_set_agreeme | gpt-5.4-2026-03-05 | A_frozen | 0.8560 | 0.6491 | -0.2069 | [-0.295, -0.125] | rejected |
| cited_span_set_agreeme | gpt-5.4-2026-03-05 | B_conservative_failure | 0.8560 | 0.6491 | -0.2069 | [-0.295, -0.125] | rejected |
| cited_span_set_agreeme | gpt-5.4-2026-03-05 | C_complete_case | 0.8560 | 0.6491 | -0.2069 | [-0.295, -0.125] | rejected |
| extracted_span_set_agr | gpt-5.4-2026-03-05 | A_frozen | 0.8533 | 0.6285 | -0.2248 | [-0.314, -0.142] | rejected |
| extracted_span_set_agr | gpt-5.4-2026-03-05 | B_conservative_failure | 0.8533 | 0.6285 | -0.2248 | [-0.314, -0.142] | rejected |
| extracted_span_set_agr | gpt-5.4-2026-03-05 | C_complete_case | 0.8533 | 0.6285 | -0.2248 | [-0.314, -0.142] | rejected |
| label_agreement | gemini-2.5-pro | A_frozen | 0.9286 | 0.8050 | -0.1236 | [-0.202, -0.052] | rejected |
| label_agreement | gemini-2.5-pro | B_conservative_failure | 0.9286 | 0.8050 | -0.1236 | [-0.202, -0.052] | rejected |
| label_agreement | gemini-2.5-pro | C_complete_case | 0.9286 | 0.8050 | -0.1236 | [-0.202, -0.052] | rejected |
| cited_span_set_agreeme | gemini-2.5-pro | A_frozen | 0.8560 | 0.6504 | -0.2055 | [-0.290, -0.125] | rejected |
| cited_span_set_agreeme | gemini-2.5-pro | B_conservative_failure | 0.8560 | 0.6504 | -0.2055 | [-0.290, -0.125] | rejected |
| cited_span_set_agreeme | gemini-2.5-pro | C_complete_case | 0.8560 | 0.6504 | -0.2055 | [-0.290, -0.125] | rejected |
| extracted_span_set_agr | gemini-2.5-pro | A_frozen | 0.8533 | 0.6330 | -0.2203 | [-0.309, -0.135] | rejected |
| extracted_span_set_agr | gemini-2.5-pro | B_conservative_failure | 0.8533 | 0.6330 | -0.2203 | [-0.309, -0.135] | rejected |
| extracted_span_set_agr | gemini-2.5-pro | C_complete_case | 0.8533 | 0.6352 | -0.2181 | [-0.307, -0.134] | rejected |
| label_agreement | amazon.nova-pro-v1-0 | A_frozen | 0.9286 | 0.8321 | -0.0965 | [-0.169, -0.033] | inconclusive |
| label_agreement | amazon.nova-pro-v1-0 | B_conservative_failure | 0.9286 | 0.8321 | -0.0965 | [-0.169, -0.033] | inconclusive |
| label_agreement | amazon.nova-pro-v1-0 | C_complete_case | 0.9286 | 0.8321 | -0.0965 | [-0.169, -0.033] | inconclusive |
| cited_span_set_agreeme | amazon.nova-pro-v1-0 | A_frozen | 0.8560 | 0.5738 | -0.2822 | [-0.376, -0.190] | rejected |
| cited_span_set_agreeme | amazon.nova-pro-v1-0 | B_conservative_failure | 0.8560 | 0.5738 | -0.2822 | [-0.376, -0.190] | rejected |
| cited_span_set_agreeme | amazon.nova-pro-v1-0 | C_complete_case | 0.8560 | 0.5738 | -0.2822 | [-0.376, -0.190] | rejected |
| extracted_span_set_agr | amazon.nova-pro-v1-0 | A_frozen | 0.8533 | 0.7010 | -0.1523 | [-0.233, -0.076] | rejected |
| extracted_span_set_agr | amazon.nova-pro-v1-0 | B_conservative_failure | 0.8533 | 0.7010 | -0.1523 | [-0.233, -0.076] | rejected |
| extracted_span_set_agr | amazon.nova-pro-v1-0 | C_complete_case | 0.8533 | 0.7010 | -0.1523 | [-0.233, -0.076] | rejected |
| label_agreement | meta.llama4-maverick | A_frozen | 0.9286 | 0.7996 | -0.1290 | [-0.215, -0.053] | rejected |
| label_agreement | meta.llama4-maverick | B_conservative_failure | 0.9286 | 0.7996 | -0.1290 | [-0.215, -0.053] | rejected |
| label_agreement | meta.llama4-maverick | C_complete_case | 0.9286 | 0.7996 | -0.1290 | [-0.215, -0.053] | rejected |
| cited_span_set_agreeme | meta.llama4-maverick | A_frozen | 0.8560 | 0.4529 | -0.4031 | [-0.509, -0.298] | rejected |
| cited_span_set_agreeme | meta.llama4-maverick | B_conservative_failure | 0.8560 | 0.4529 | -0.4031 | [-0.509, -0.298] | rejected |
| cited_span_set_agreeme | meta.llama4-maverick | C_complete_case | 0.8560 | 0.4529 | -0.4031 | [-0.509, -0.298] | rejected |
| extracted_span_set_agr | meta.llama4-maverick | A_frozen | 0.8533 | 0.5317 | -0.3217 | [-0.420, -0.225] | rejected |
| extracted_span_set_agr | meta.llama4-maverick | B_conservative_failure | 0.8533 | 0.5317 | -0.3217 | [-0.420, -0.225] | rejected |
| extracted_span_set_agr | meta.llama4-maverick | C_complete_case | 0.8533 | 0.5317 | -0.3217 | [-0.420, -0.225] | rejected |
