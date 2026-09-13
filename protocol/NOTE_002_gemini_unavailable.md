# Protocol note 002 — `gemini-2.5-pro` not callable on the public API

**Date:** 2026-09-12 (after primary results, before replication execution)
**Effect:** the Gemini condition is **excluded** from the replication subset.

## What happened

The frozen replication plan (note 001) specified reaching `gemini-2.5-pro`
through the direct Gemini API with API-key authentication. That key
authenticates successfully and `models/gemini-2.5-pro` appears in its model
listing with `generateContent` among its supported methods.

But every `generateContent` call returns **HTTP 404**:

> This model models/gemini-2.5-pro is no longer available to new users.
> Please update your code to use models/gemini-3.1-pro-preview

Confirmed on both `v1beta` and `v1`. The model is listed but not callable with
this account.

## Decision: exclude, do not substitute

`gemini-3.1-pro-preview` is a **different model**. Running it and reporting the
result as a replication of the `gemini-2.5-pro` condition would compare two
different models while claiming to compare serving paths. The frozen mapping
says explicitly: *"Where a condition has no faithful public equivalent that is
documented here as a gap rather than papered over with a near-neighbour."*

That rule applies exactly here. The condition is recorded as **not evaluable**.

## Interaction with the mutable-alias limitation

This is the same underlying fact that note 001 flagged as a caveat, now
realised in a stronger form. `gemini-2.5-pro` was never a pinned snapshot on
either path. Google has since restricted it to existing users and is steering
new traffic to a successor.

Two consequences:

1. **The replication cannot evaluate this condition at all.** There is no
   attributable comparison to make.
2. **The confirmatory result for this condition is itself less durable than the
   others.** the managed execution path served *something* under that alias during the
   2026-09-09 → 2026-09-12 run, and that something is no longer reachable for
   verification. The confirmatory measurement stands — it was made, logged, and
   provenance-checked — but it cannot be re-verified against the public API, now
   or later.

This is a concrete instance of the reproducibility hazard the paper already
describes. It should be reported as evidence for the argument, not buried as an
inconvenience: **a mutable model identifier can become unverifiable within days
of the experiment that used it.**

## Replication coverage after this note

| Condition | Status |
|---|---|
| `gpt-4o-2024-11-20` (incumbent) | available — immutable id, attributable |
| `gpt-5.4-2026-03-05` | available — immutable id, attributable |
| `gemini-2.5-pro` | **NOT EVALUABLE** — withdrawn from new users |
| `amazon.nova-pro-v1:0` | **NOT EVALUABLE** — no direct Bedrock access exists |
| `meta.llama4-maverick-17b-instruct-v1:0` | **NOT EVALUABLE** — no direct Bedrock access exists |

### Why the two Bedrock conditions are not evaluable

These were initially recorded as "AWS credentials expired". That was wrong. The
two AWS profiles on the execution host hold static *session* credentials
written 2026-03-27, with no `~/.aws/config`, no SSO configuration and no
credential helper installed — and the researcher has never configured or used
Bedrock outside the managed execution path. The stale credentials belong to an
unrelated context.

There is therefore **no direct Bedrock access to refresh**. Evaluating these two
conditions would require standing up a personal AWS account, enabling Bedrock,
requesting per-model access for both, and incurring separate billing. That is
not a credential-refresh away; it is a different provisioning exercise.

They are recorded as structural gaps rather than pending work.

**2 of 5 conditions replicable.** Both are OpenAI, and critically one is the
incumbent, so `W_A` is computable and the same-provider
GPT-4o → GPT-5.4 migration can be compared across serving paths with immutable
identifiers on both sides.

The three unevaluated conditions are recorded as gaps. The frozen task subset
(`replication_subset.json`, hash `ebaba1cb…`) is unchanged.
