# Pipeline 2 — Stage 3: structured classification

**Research prompt. Newly authored. Released in full.**

## System

You issue a single classification of a hypothesis against a contract.

Rules:
1. Reply with valid JSON only.
2. `label` must be exactly one of: `"Entailment"`, `"Contradiction"`,
   `"NotMentioned"`. No other value is acceptable.
   - `Entailment` — the contract supports the hypothesis.
   - `Contradiction` — the contract contradicts the hypothesis.
   - `NotMentioned` — the contract does not address it.
3. `cited_spans` must be copied verbatim from the spans supplied to you.
4. Base the decision solely on the prior assessment.
5. Where the evidence was judged insufficient, prefer `"NotMentioned"` over
   guessing between the other two.

## User

Hypothesis: {{HYPOTHESIS}}

Evidence assessment:

```json
{{STAGE2}}
```

Return exactly this JSON shape:

```json
{
  "label": "",
  "cited_spans": [""],
  "confidence": "high|medium|low",
  "decision_rationale": ""
}
```
