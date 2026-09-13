# Simultaneous inference across the 12 P2 primary cells

Pointwise 95% intervals each cover their own Delta with 95%
probability; across 12 cells that does not control simultaneous
coverage. This constructs max-|t| simultaneous bands using **common**
bootstrap task resamples, so the dependence between cells is
preserved rather than assumed away.

- cells: **12**
- tasks: **60**
- bootstrap replicates: **10000** (seed `20260803`)
- simultaneous critical value: **2.7839**  (pointwise would be ~1.96)
- mean width inflation: **1.335x**

This is a robustness analysis. It does not replace the pointwise
intervals as the paper's primary inference.

## Verdict changes

**2 of 12 verdicts change** under simultaneous
intervals at the frozen tolerance 0.05.

| property | candidate | frozen | simultaneous | pointwise CI | simultaneous CI |
|---|---|---|---|---|---|
| label_agreement | gemini-2.5-pro | rejected | inconclusive | [-0.202, -0.052] | [-0.226, -0.022] |
| label_agreement | meta.llama4-maverick-1 | rejected | inconclusive | [-0.215, -0.053] | [-0.237, -0.021] |

## Does the span-vs-label conclusion survive?

- span cells rejected, pointwise: **8/8**
- span cells rejected, simultaneous: **8/8**
- mean |Delta| spans **0.2521** vs labels **0.1035**

## All cells

| property | candidate | Delta | pointwise CI | simultaneous CI | inflation | frozen | simultaneous |
|---|---|---|---|---|---|---|---|
| label_agreement | gpt-5.4-2026-03-05 | -0.0648 | [-0.136, -0.003] | [-0.153, +0.023] | 1.332x | inconclusive | inconclusive |
| cited_span_set_agreement | gpt-5.4-2026-03-05 | -0.2069 | [-0.295, -0.125] | [-0.320, -0.093] | 1.339x | rejected | rejected |
| extracted_span_set_agree | gpt-5.4-2026-03-05 | -0.2248 | [-0.314, -0.142] | [-0.341, -0.108] | 1.355x | rejected | rejected |
| label_agreement | gemini-2.5-pro | -0.1236 | [-0.202, -0.052] | [-0.226, -0.022] | 1.357x | rejected | inconclusive |
| cited_span_set_agreement | gemini-2.5-pro | -0.2055 | [-0.290, -0.125] | [-0.315, -0.096] | 1.327x | rejected | rejected |
| extracted_span_set_agree | gemini-2.5-pro | -0.2203 | [-0.309, -0.135] | [-0.336, -0.105] | 1.323x | rejected | rejected |
| label_agreement | amazon.nova-pro-v1-0 | -0.0965 | [-0.169, -0.033] | [-0.184, -0.009] | 1.292x | inconclusive | inconclusive |
| cited_span_set_agreement | amazon.nova-pro-v1-0 | -0.2822 | [-0.376, -0.190] | [-0.405, -0.159] | 1.322x | rejected | rejected |
| extracted_span_set_agree | amazon.nova-pro-v1-0 | -0.1523 | [-0.233, -0.076] | [-0.253, -0.051] | 1.287x | rejected | rejected |
| label_agreement | meta.llama4-maverick | -0.1290 | [-0.215, -0.053] | [-0.237, -0.021] | 1.337x | rejected | inconclusive |
| cited_span_set_agreement | meta.llama4-maverick | -0.4031 | [-0.509, -0.298] | [-0.547, -0.259] | 1.365x | rejected | rejected |
| extracted_span_set_agree | meta.llama4-maverick | -0.3217 | [-0.420, -0.225] | [-0.457, -0.186] | 1.389x | rejected | rejected |
