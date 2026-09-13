# Amendment 001 — uniform `max_tokens` 2048 → 8192

**Type:** pre-experiment protocol amendment
**Date:** 2026-09-09
**Discovery point:** 82 / 20,160 calls (0.4%)
**Status:** applied before the confirmatory run began

## What changed

| | |
|---|---|
| Old value | `2048` |
| New value | `8192` |
| Scope | **all five model conditions, uniformly** |
| Per-model ceilings | **explicitly rejected** |

## Why

`2048` was an **implementation constant in the runner**, not a frozen
scientific parameter. It appears nowhere in `protocol_spec.json`; it was a
default I chose when writing `run_experiment.py`.

Early QC found `gemini-2.5-pro` terminating with `finish_reason=length` on
**15 of 28 calls (54%)**, producing truncated, unparseable JSON. No other model
truncated even once:

| Model | Truncated |
|---|---|
| **gemini-2.5-pro** | **15/28 (54%)** |
| gpt-4o-2024-11-20 | 0/12 |
| gpt-5.4-2026-03-05 | 0/20 |
| us.amazon.nova-pro-v1:0 | 0/12 |
| us.meta.llama4-maverick-17b-instruct-v1:0 | 0/10 |

**Cause.** Gemini spends most of its completion budget on internal reasoning
tokens. Observed text-per-token ratios:

- gemini-2.5-pro: 2,044 tokens → **261 characters** (ratio 0.13); worst cases 0.12–0.19
- gpt-4o-2024-11-20: 288 tokens → 1,194 characters (ratio ~4.2–5.5)

Gemini needs roughly **30× more budget per character of visible output**.

## Why this had to be fixed rather than tolerated

Left at 2048, the grid would have assigned `gemini-2.5-pro` a ~54%
schema-violation rate that is **an artifact of the output ceiling, not model
behaviour**, and starved its M2/M3 content metrics of parseable text. The
migration verdict for that candidate would have been substantially an artifact
of an arbitrary implementation constant.

## Why uniform, not per-model

A per-model ceiling would make the serving configuration non-uniform across the
comparison. The study's claim is about migrating between models under a *fixed*
application configuration; varying the ceiling per model would confound model
identity with configuration and weaken exactly the comparison being made.

8192 is applied identically to all five conditions.

## Disposition of the 82 aborted calls

**Excluded from every confirmatory analysis.** Preserved for auditability at
`results/aborted_qc_run/` with `ABORTED_RUN_NOTICE.json` and ledger SHA-256
`94de7f82877138cd360e815ca6cdb210072e7af61f0057c72b7b236c93aa836c

> **Public mirror note.** The private artifact records this ledger's SHA-256 as
> `01c641f8db8735df5c0da9cb697b49e43cfea0028cd4b91ff159a97a135cccf4`.
> In this public mirror the digest differs because the incumbent condition's
> internal vendor-routing request id was replaced by its public model id in 12
> of the 82 quarantined records. All 82 records are present and no other field
> changed; these records remain excluded from every reported result.`.

- 82 calls, 0 errors, 0 retries, 0 provenance flags
- 53,076 input / 74,316 output tokens
- **No scientific result from these calls is used.**
- A guard in `tests/test_no_aborted_data.py` fails if the aborted ledger is
  merged into the confirmatory results directory.

The confirmatory experiment restarts from call 0 with an empty ledger.

## What did NOT change

Corpora, prompts, model IDs, repetition counts, estimands, tolerances,
retry/exclusion rules, randomization seed and schedule, and metric definitions
are all unchanged. Corpus and prompt hashes are asserted identical at re-freeze.

## Verification performed before restart

A QC check re-ran already-used task/model combinations at 8192 and confirmed
Gemini no longer materially truncates, JSON is complete and parseable, other
models behave normally, and provenance remains correct. Per the instruction, if
8192 had still produced meaningful truncation the run would have stopped for
review rather than the ceiling being changed again.
