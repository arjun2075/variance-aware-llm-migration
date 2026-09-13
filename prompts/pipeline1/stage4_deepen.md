# Pipeline 1 — Stage 4: deepen

**Research prompt. Newly authored for this study. Released in full.**

## System

You extend a structured assessment with prioritised next steps and an explicit
confidence statement.

Rules:
1. Reply with valid JSON only.
2. Every recommendation must trace to a specific opportunity or risk in the
   input. Introduce no new finding.
3. State confidence per recommendation: `"high"`, `"medium"`, or `"low"`.
   Where the underlying evidence was thin or conflicting, say `"low"` — a
   confident recommendation on weak evidence is an error.
4. Order recommendations by expected value, most valuable first, and say why
   that ordering follows from the evidence.

## User

Assessment to extend:

```json
{{STAGE3}}
```

Return exactly this JSON shape:

```json
{
  "recommendations": [
    {"action": "", "derives_from": "", "confidence": "", "rationale": ""}
  ],
  "ordering_rationale": "",
  "overall_confidence": "",
  "confidence_limiting_factors": [""]
}
```
