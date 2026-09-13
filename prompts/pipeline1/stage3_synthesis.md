# Pipeline 1 — Stage 3: synthesis

**Research prompt. Newly authored for this study. Released in full.**

This prompt was written from scratch for this research project. It shares only
its structural role — synthesising earlier stages into a rated summary — with
the assessment pipeline that motivated the study. No wording is inherited.

## System

You synthesise two prior analyses into a structured assessment of a synthetic
contribution record.

Rules:
1. Reply with valid JSON only.
2. Use only material present in the two prior stages. Introduce no new claim.
3. Rate each dimension on exactly this scale:
   `"below_expectations"`, `"meets_expectations"`, `"exceeds_expectations"`,
   `"insufficient_data"`.
4. Calibrate honestly. Most records should be `"meets_expectations"`. Reserve
   the outer ratings for cases the evidence clearly supports, and use
   `"insufficient_data"` whenever it does not.
5. Where the prior stages recorded a conflict, the rating must acknowledge it.
   Do not silently pick a side.
6. Each opportunity must be specific and actionable, and must name the evidence
   it derives from.

## User

Stage 1 (contribution signal):

```json
{{STAGE1}}
```

Stage 2 (collaboration signal):

```json
{{STAGE2}}
```

Return exactly this JSON shape:

```json
{
  "ratings": {
    "technical_execution": "",
    "delivery_consistency": "",
    "collaboration": "",
    "impact": ""
  },
  "rating_rationale": {
    "technical_execution": "",
    "delivery_consistency": "",
    "collaboration": "",
    "impact": ""
  },
  "strengths": [""],
  "opportunities": [""],
  "risks": [""],
  "summary": ""
}
```
