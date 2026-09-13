# Required methods / reproducibility disclosures

Items that MUST appear in the paper. Each is a deviation, limitation, or
judgement call that a reader needs in order to evaluate the work. This file
exists so none of them is lost between execution and writing.

---

## 1. Amendment 001 — output ceiling raised mid-bring-up

**Must be described transparently in the reproducibility/methods section.**

Suggested content:

> An initial 82-call quality-control run exposed a uniform output-token ceiling
> (2,048) that truncated `gemini-2.5-pro` on 15 of 28 calls (54%), while no
> other model truncated once. The cause is that Gemini expends most of its
> completion budget on internal reasoning tokens (~0.13 characters of visible
> output per completion token, against ~4.5 for GPT-4o), so the ceiling
> curtailed its visible answer rather than its reasoning. Left in place, this
> would have assigned that candidate a schema-violation rate that was an
> artifact of the output budget rather than a property of the model. The
> ceiling was raised uniformly to 8,192 for all five conditions — per-model
> ceilings were rejected because they would have made the serving configuration
> non-uniform across the comparison. The 82-call run was quarantined and
> excluded from all analysis, and the confirmatory experiment was restarted
> from zero.

Why this is scientifically defensible, and worth stating as such:

- discovered during **execution QC**, not from outcome analysis;
- the ceiling was an **implementation constant**, not a pre-registered
  scientific parameter;
- applied **uniformly** to all five conditions;
- **documented before** the confirmatory restart;
- followed by a **clean restart from call 0**;
- **no corpus, prompt, model id, repetition count, estimand, tolerance, retry
  rule or randomization change** accompanied it.

Artifacts: `protocol/AMENDMENT_001_max_tokens.md`,
`results/qc_ceiling_check.json`, `results/aborted_qc_run/` (ledger SHA-256
`01c641f8db8735df5c0da9cb697b49e43cfea0028cd4b91ff159a97a135cccf4`).

---

## 2. `gemini-2.5-pro` is not a pinned snapshot

the managed execution path returns the alias unchanged rather than resolving it to a dated
snapshot. The served weights may therefore change during or between runs, and
this study **cannot detect that from the returned identifier alone**. This is a
reproducibility limitation of that condition specifically and must be stated,
not buried. The other four conditions return immutable versioned identifiers.

## 3. Canonical model identifiers are rewritten by the managed execution path

Three of five requested identifiers differ from what is returned:

| Requested | Returned |
|---|---|
| `gpt-4o-2024-11-20` | `gpt-4o-2024-11-20` |
| `amazon.nova-pro-v1-0` | `us.amazon.nova-pro-v1:0` |
| `meta.llama4-maverick-17b-instruct-v1-0` | `us.meta.llama4-maverick-17b-instruct-v1:0` |

The mapping was established by live probe before the run
(`protocol/canonical_model_map.json`) and provenance is checked against it per
call. Report the canonical identifiers, not the catalog aliases.

## 4. Execution is strictly serial, not concurrent

the managed execution path does not permit concurrent calls. The design intent of
randomized/interleaved execution is preserved — the schedule is a seeded
permutation over (task × model × repetition) — but it is walked one call at a
time, with a ≥2 s inter-call interval (15 s for Bedrock-backed families).
Published per-Experience RPM/TPM limits were not obtainable, so pacing is
interval-based rather than budget-based. State this rather than implying a
tuned concurrency figure.

## 5. Transport goes through a transport helper

Calls are issued via a Go binary built against the service's own client,
because a plain HTTPS client is rejected at the managed transport layer. This is
execution infrastructure and changes no experimental condition, but it should
be mentioned so the replication package is intelligible.

## 6. Pipeline 1 declares no equivalence tolerance

P1 reports tolerance/effect curves and issues **no headline equivalence
verdict**, because no application-grounded tolerance exists for its behavioral
metrics. This is a deliberate departure from the pilot study's universal ±0.10
threshold and should be presented as a methodological position, not an
omission.

## 7. Study 0 is a pilot, never pooled

The recovered 8-profile / 200-run experiment motivates this work and supplied
the repetition-budget and task-count simulations. Its results are never merged
with the confirmatory grid.

## 8. Replication subset was frozen before any results were seen

The public-API replication subset (10 P1 + 10 P2 tasks) and its model mapping
were selected and hashed **while the confirmatory grid was still running and no
agreement, correctness or equivalence result had been computed or viewed**
(`protocol/replication_subset.json`, selection SHA-256
`ebaba1cb3d17fefbe65b29b61e0a769fde9c7882fe5bc61cebecfd2cd3b791b7`). State this
ordering: a subset chosen after seeing results would make a "reproduces"
verdict uninterpretable.

## 9. The replication cannot cover all five conditions

| Condition | Public equivalent | Status |
|---|---|---|
| gpt-4o-2024-11-20 | same | exact |
| amazon.nova-pro-v1:0 | same Bedrock profile | exact |
| meta.llama4-maverick-...-v1:0 | same Bedrock profile | exact |
| gpt-5.4-2026-03-05 | same id expected | unverified on a public account |
| gemini-2.5-pro | Google AI Studio / Vertex | **outside the frozen provider set** |

Gemini is not reachable via OpenAI, Anthropic or Bedrock, which are the three
providers the protocol named. Either add Google as a fourth replication
provider or exclude that condition — and say which. Do not substitute a
near-neighbour model and present it as the same condition.

Note also that the protocol lists Anthropic as a replication provider, but the
confirmatory matrix contains no Anthropic condition, so there is nothing to
replicate there. Adding one would not correspond to any measured condition.

Even for exact id matches, the public API and the managed execution path are different serving
paths; the replication tests whether QUALITATIVE conclusions hold, not whether
numbers match.

## 10. Execution pacing was conservative, not measured

The confirmatory grid ran strictly serially: each call waited for the previous
response, then slept (2 s general, 15 s for Bedrock-backed families). Those
intervals were **conservative defaults chosen from an operational note, not
measured limits**. In 14,086 calls — including 5,054 Bedrock calls — **zero 429
responses were observed**. The 15 s Bedrock floor alone accounted for roughly
15.6 h of the ~48 h wall-clock.

A replicator should not infer that these intervals are required. A scheduler
that spaces request *starts* while allowing a bounded number of requests in
flight would very likely be substantially faster. It was not adopted mid-run
because latency and retry counts are reported operational metrics and changing
the regime partway would have split that data.

## 11. Pipeline 2 gold data never reaches the model

Gold labels and evidence spans are used only for post-hoc scoring;
`inference_view()` strips them before prompt rendering, and this is asserted by
tests and re-checked against every rendered prompt in the mock run.
