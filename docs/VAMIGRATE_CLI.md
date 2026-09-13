# `vamigrate` — variance-aware migration test

A small reference implementation of the paper's procedure. It consumes
**precomputed model outputs only**: it never invokes a model and makes no
network call.

```bash
python analysis/vamigrate.py compare \
    --incumbent inc.jsonl --candidate cand.jsonl \
    --metric exact --tolerance 0.05
```

## What it computes

| Quantity | Meaning |
|---|---|
| `W_A` | incumbent self-agreement, over **distinct** repetition pairs |
| `C_AB` | incumbent–candidate agreement over the full cross product |
| `Delta` | `C_AB − W_A` — the migration effect |
| CI | two-level cluster bootstrap (tasks, then repetitions) |
| verdict | three-way classification against `--tolerance` |

The statistics come from `vaml.analysis.migration` and `vaml.analysis.metrics`,
the same tested implementations used for the paper's results. No formula is
duplicated in the CLI.

## Input format

JSONL, one record per line:

```json
{"task_id": "t1", "repetition": 1, "value": "Entailment"}
{"task_id": "t1", "repetition": 2, "value": "Entailment"}
```

Required: `task_id`, `repetition` (integer), `value`.

`value` may be a scalar (use `--metric exact` or `ordinal`) or a list (use
`jaccard`, `multiset`, or `sequence`).

Optional per-record fields are summarised when present:

| Field | Effect |
|---|---|
| `correct` (bool) | reports per-side accuracy and `accuracy_delta` |
| `invariant_ok` (bool) | reports an invariant satisfaction rate |

The incumbent file needs **at least two repetitions per task** — without them
`W_A` cannot be estimated, and the tool refuses rather than guessing.

## Options

| Flag | Default | Purpose |
|---|---|---|
| `--metric` | `exact` | `exact`, `ordinal`, `jaccard`, `multiset`, `sequence` |
| `--tolerance` | — | enables the verdict; omit for effects only |
| `--replicates` | 10000 | bootstrap replicates |
| `--seed` | 20260803 | deterministic given the same inputs |
| `--json` | off | machine-readable output |

## Example

```
$ python analysis/vamigrate.py compare \
    --incumbent tests/fixtures/incumbent.jsonl \
    --candidate tests/fixtures/candidate.jsonl \
    --metric exact --tolerance 0.05

tasks                 12
incumbent repetitions 5
candidate repetitions 3
metric                exact

W_A                   0.6833   (120 pairs)
C_AB                  0.4500   (180 pairs)
Delta = C_AB - W_A    -0.2333
95% CI                [-0.4755, +0.0322]

tolerance             0.05
verdict               INCONCLUSIVE
accuracy_delta        -0.1167

incumbent accuracy    0.7833
candidate accuracy    0.6667
```

## The vacuity warning

If `tolerance >= W_A`, the tool warns:

```
WARNING: tolerance 0.8 >= W_A 0.6833: the test cannot exclude C_AB = 0,
so it is vacuous on the negative side
```

Because agreement is bounded in `[0,1]`, `Delta >= -W_A` always. When the
tolerance is at least `W_A`, even *complete* disagreement between incumbent and
candidate satisfies it — the test cannot fail. A separate warning fires when
`W_A = 0`, where no migration verdict is meaningful at all.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | malformed input (message on stderr) |

Rejected inputs include: missing file, invalid JSON, missing required field,
non-integer repetition, duplicate repetition for a task, no overlapping
`task_id`, fewer than two incumbent repetitions, and unknown metric.

## Scope

This is a reproducible reference implementation, not a product. It deliberately
does no orchestration, no model invocation, and no result storage.
