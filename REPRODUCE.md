# Reproduction guide

Every command below runs from the repository root and requires **no model or
API calls**. All randomness is seeded at `20260803`.

Scientific analysis frozen at commit `3652060`.

---

## 1. Install

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock.txt
```

Verify the interpreter:

```bash
python --version   # expect Python 3.11.14
```

## 2. Run all tests

```bash
pytest tests/ protocol/ -q      # or simply: pytest
```

Expected: **451 passed, 1 skipped**.

Run this from a **git checkout**. Several tests are repository-hygiene guards
that enumerate files with `git ls-files` / `git status`; in a plain unpacked
directory with no `.git`, 22 of them fail with `exit status 128`. That is the
absent git metadata, not a defect in the code or data. To run them from the
extracted archive, initialise a throwaway repository first:

```bash
git init -q . && git add -A && git -c user.email=a@b -c user.name=a commit -qm baseline
```

The stricter pre-publication guard is skipped by default; enable it with:

```bash
PUBLIC_RELEASE=1 pytest tests/test_no_proprietary_content.py -q
```

## 3. Verify the frozen state

```bash
python protocol/freeze_protocol.py verify --lock protocol/protocol_lock.json
```

**This prints `PROTOCOL VERIFICATION: FAIL`, and that is the expected result for
this public artifact.** It is a documented consequence of public-release
sanitization, not drift and not a defect. The lock is deliberately left
unfixed: re-pinning its hashes to match the sanitized files would make the
summary line green while destroying the audit signal the lock exists to
provide. Read the individual lines rather than the verdict.

**What verifies unchanged — the part that matters scientifically:**

- **All 16 task-corpus hashes.** No corpus and no prompt was altered.
- **All 1,320 numerical analysis values.** Re-running §4 from this tree
  regenerates `results/analysis/pairwise_results.json` bit-for-bit
  (`2195d0d414409db0...`). Against the private frozen artifact, **zero** numeric
  values differ — the only differences are 56 occurrences of a model-id label.
- Seeds, estimands, analysis semantics and the recorded ledger.

**Why hashes moved.** Six infrastructure/source files had docstrings and
comments rewritten to remove corporate execution-environment identifiers:
`src/vaml/adapters/shim.py`, `src/vaml/models.py`,
`src/vaml/orchestration/rate_limits.py`, `scripts/run_experiment.py`,
`scripts/qc_ceiling_check.py`, `scripts/smoke_test.py`. The rewrites are
textual only and touch no executable logic. Two of these
(`shim.py`, `run_experiment.py`) additionally carry the documented mid-run
auth-recovery fix from commit `e30c78e`, recorded in `EXECUTION_REPORT.md` §7,
which altered execution transport only and no experimental condition.

`protocol/PROTOCOL.md` and four sections of `protocol/protocol_spec.json`
(`execution_environment`, `model_conditions`, `protocol_id`,
`public_api_replication`) also differ. These are identifier substitutions only
— the execution environment's name, the incumbent's model-id label, and the
protocol id suffix. **No experimental parameter changed**: repetition counts,
task counts, estimands, tolerances, retry and exclusion rules, and the
randomized schedule are all identical to the frozen protocol.

Compiled `__pycache__` entries present in the private lock were removed here,
since byte-caches are regenerated on import and are not shipped.

## 4. Reproduce the confirmatory analysis

Reads the persisted ledger; no model calls.

```bash
export REV=e8c3b32edf5434bc2275fc9bab85f82640a19130

python scripts/run_analysis.py \
    --ledger results/run/calls.jsonl \
    --embedding-revision $REV \
    --out results/analysis                      # ~15 min

python scripts/run_extended_analysis.py \
    --embedding-revision $REV \
    --out results/analysis                      # ~35 min
```

Outputs `pairwise_results.json`, `execution_summary.json` and
`extended_analysis.json`. Compare against the committed copies — they should
match to within float tolerance.

## 5. Reproduce the strengthening analyses

Fast (seconds to minutes):

```bash
python analysis/tolerance_nonvacuity.py
python analysis/plot_tolerance_decision_curves.py
python analysis/migration_baseline_ablations.py
python analysis/contractnli_subset_representativeness.py   # needs the dataset
```

Moderate (minutes to ~1 h):

```bash
python analysis/single_run_oracle_instability.py           # ~5 min
python analysis/simultaneous_inference.py                  # ~10 min
python analysis/invalid_output_sensitivity.py              # ~10 min
python analysis/evaluation_budget_study.py                 # ~60 min
```

Long (hours) — reduce with `--n-sim` / `--boot-reps` for a smoke run:

```bash
python analysis/bootstrap_coverage_simulation.py           # ~3 h at 2000x200
python analysis/bootstrap_resolution_sensitivity.py        # ~85 min

# quick smoke versions
python analysis/bootstrap_coverage_simulation.py --n-sim 50 --boot-reps 100 --scenarios 2
```

## 6. Regenerate manuscript figures

Figures are emitted by the scripts above into `figures/`:

| Figure | Produced by |
|---|---|
| `tolerance_nonvacuity.{pdf,png}` | `analysis/tolerance_nonvacuity.py` |
| `p2_tolerance_decision_curves.{pdf,png}` | `analysis/plot_tolerance_decision_curves.py` |
| `baseline_ablations.{pdf,png}` | `analysis/migration_baseline_ablations.py` |
| `single_run_oracle_instability.{pdf,png}` | `analysis/single_run_oracle_instability.py` |
| `evaluation_budget_tasks.{pdf,png}` | `analysis/evaluation_budget_study.py` |
| `evaluation_budget_repetitions.{pdf,png}` | `analysis/evaluation_budget_study.py` |
| `bootstrap_coverage.{pdf,png}` | `analysis/bootstrap_coverage_simulation.py` |

Regenerate the fast ones in one pass:

```bash
python analysis/tolerance_nonvacuity.py && \
python analysis/plot_tolerance_decision_curves.py && \
python analysis/migration_baseline_ablations.py
```

## 7. `vamigrate` smoke test

The documented one-line check that the CLI works end to end:

```bash
python analysis/vamigrate.py compare \
    --incumbent tests/fixtures/incumbent.jsonl \
    --candidate tests/fixtures/candidate.jsonl \
    --metric exact --tolerance 0.05 --replicates 2000
```

Expected output:

```
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

Machine-readable form: add `--json`.

Non-vacuity warning (fires when `tau >= W_A`):

```bash
python analysis/vamigrate.py compare \
    --incumbent tests/fixtures/incumbent.jsonl \
    --candidate tests/fixtures/candidate.jsonl \
    --metric exact --tolerance 0.80 --replicates 500
# WARNING: tolerance 0.8 >= W_A 0.6833: the test cannot exclude C_AB = 0 ...
```

## 8. Optional: rebuild the Pipeline 2 corpus

Only needed if you want to verify the sampling itself. Requires the
ContractNLI dataset obtained under its own terms (see `README.md` §8).

```bash
python scripts/validate_contractnli.py --source data/raw/contractnli/train.json
python scripts/build_p2_corpus.py     --source data/raw/contractnli/train.json
```

Deterministic under seed 20260803; reproduces the committed corpus hashes.

## 9. Expected runtimes

| Step | Time |
|---|---|
| Tests | ~20 s |
| Primary analysis | ~15 min |
| Extended analysis | ~35 min |
| All fast strengthening analyses | ~2 min |
| Evaluation budget | ~60 min |
| Bootstrap coverage (full) | ~3 h |
| Bootstrap resolution sensitivity | ~85 min |

Measured on an Apple Silicon laptop, single core.
