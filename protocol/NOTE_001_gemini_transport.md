# Protocol note 001 — Gemini transport for the replication subset

**Type:** protocol note, not an amendment
**Date:** 2026-09-11
**Recorded BEFORE any scientific result was inspected** (confirmatory grid at
70.3%, 14,175/20,160 calls; no agreement, correctness or equivalence value had
been computed or viewed)

## Decision

The direct-provider replication subset will reach `gemini-2.5-pro` through the
**Gemini API with API-key authentication** (`google.genai`), not through Vertex
AI service-account authentication.

## Why this is a note rather than an amendment

The freeze exists to prevent **outcome-dependent** choices. This decision is
not outcome-dependent in any respect:

- no scientific result had been computed or seen when it was made;
- it follows from a plain infrastructure fact — `gemini-2.5-pro` is not served
  by OpenAI, Anthropic or Bedrock, the three providers the protocol named — which
  would hold whatever the data showed;
- it changes no task, prompt, model identity, repetition count, estimand,
  metric, tolerance or randomization.

Contrast with Amendment 001, which changed an execution parameter *mid-run*
after truncation behaviour had been observed. That required the full amendment
treatment. This does not.

## Why the Gemini API rather than Vertex

Vertex service-account auth is non-functional on the execution host:
`gcloud auth print-access-token` fails with
`SSLCertVerificationError: unable to get local issuer certificate`.

This is **not** a network or certificate problem, and the initial diagnosis of
"corporate TLS interception" was wrong:

- `curl` reaches `oauth2.googleapis.com` normally (HTTP 404 on a bare GET, the
  expected response), with and without the corporate CA bundle;
- gcloud's own interpreter reaches the same endpoint normally;
- only gcloud's bundled auth path fails, and setting
  `core/custom_ca_certs_file` does not help.

The fault is therefore internal to the gcloud auth stack. Rather than debug it,
the replication uses the API-key path, which is independently demonstrated to
work on this host by another application on the same machine.

## Consequence for the claim — the part that matters

`gemini-2.5-pro` is a **mutable alias on both paths**. the managed execution path returned the
alias unchanged rather than resolving it to a dated snapshot, and the public
Gemini API likewise exposes no immutable identifier for it.

Therefore, if the replication shows the Gemini condition behaving differently
from the confirmatory run, that difference **cannot be attributed** to serving
path rather than to Google having changed the weights behind the alias in the
interval. The two explanations are not separable with the information available.

For the other four conditions the identifiers are immutable, so a divergence is
attributable to the serving path.

This asymmetry must be stated wherever the replication is reported. The Gemini
replication result is informative as a null check — if it agrees, that is mild
evidence of stability across both dimensions at once — but it cannot support a
directional claim about managed execution path versus public serving.

## Coverage after this note

| Condition | Replication transport | Attributable divergence? |
|---|---|---|
| gpt-4o-2024-11-20 | OpenAI public API | yes (immutable id) |
| gpt-5.4-2026-03-05 | OpenAI public API | yes, if the snapshot exists publicly |
| gemini-2.5-pro | **Gemini API (API key)** | **no — mutable alias both sides** |
| us.amazon.nova-pro-v1:0 | Bedrock, personal account | yes (immutable id) |
| us.meta.llama4-maverick-…-v1:0 | Bedrock, personal account | yes (immutable id) |

## Unchanged

The replication subset itself — 10 P1 and 10 P2 task ids — was frozen and
hashed earlier (`protocol/replication_subset.json`, selection SHA-256
`ebaba1cb3d17fefbe65b29b61e0a769fde9c7882fe5bc61cebecfd2cd3b791b7`) and is not
revisited here. Repetition counts remain 8 incumbent / 5 candidate.

The replication runs **regardless of the primary outcome**.
