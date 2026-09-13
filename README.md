# Variance-Aware Regression Testing for Model Migration in Compound LLM Pipelines

Reproducibility artifact for the IEEE TSE submission.

**Scientific analysis frozen at commit `3652060`.** This repository reproduces
every reported statistic from persisted model outputs. **Ordinary reproduction
requires no model or API calls.**

---

## 0. Two different things you might want to do

|   | Analysis reproduction | Model-call re-execution |
|---|---|---|
| What it does | Recomputes every reported statistic, figure and table from the persisted ledger of 20,160 recorded calls | Issues fresh calls to language models and builds a new ledger |
| Needed to check the paper's claims? | **Yes — this is the supported path** | **No** |
| Requires API keys or credentials? | **No** | Yes — your own |
| Requires network access? | No (one optional embedding model download) | Yes |
| Cost | Free | You pay your providers |
| Determinism | Bit-for-bit: `pairwise_results.json` hashes to `2195d0d414409db0...` | Not reproducible — model outputs vary, and one condition was a mutable alias |
| How | `REPRODUCE.md` §§3-6 | `scripts/run_experiment.py`, after supplying your own adapter |

**Analysis reproduction is fully supported and self-contained.** Everything the
paper reports is recomputed from `results/run/calls.jsonl`, which is included.

**Model-call re-execution is not necessary to reproduce any reported
statistic,** and it is not expected to reproduce the same numbers: the study's
whole subject is that these pipelines vary run to run. The original runs were
executed through a managed execution path whose transport component is not part
of this public artifact (see §11). To re-execute, supply your own provider
endpoints and credentials and implement a `ProviderAdapter`
(`src/vaml/adapters/base.py`); `src/vaml/adapters/public.py` shows a direct
public-API implementation.

---

## 1. What this repository reproduces

For an incumbent model **A** and candidate **B**, the study asks whether the
candidate changes an application property by more than the incumbent's own
run-to-run variation. The primary estimand is pairwise and directional:

```
Delta(A -> B) = C_AB - W_A
    W_A  = incumbent self-agreement, over DISTINCT repetition pairs only
    C_AB = incumbent-candidate agreement over the full cross product
```

The confirmatory experiment executed **20,160 model calls / 5,040 runs** across
two compound pipelines, one incumbent and four candidates, at 8 incumbent and 5
candidate repetitions over 60 primary tasks per pipeline (plus 20 pre-frozen
stress tasks per pipeline).

This artifact reproduces, from the persisted call ledger:

- the primary pairwise migration results and bootstrap intervals
- the correctness x behaviour quadrant decomposition
- stress-set, leave-one-task-out, execution-order and compliance analyses
- all strengthening analyses (tolerance non-vacuity, bootstrap coverage
  simulation, tolerance decision curves, baseline ablations, single-run oracle
  instability, evaluation-budget study, simultaneous inference, invalid-output
  sensitivity, subset representativeness)
- every figure and table

## 2. Directory structure

```
analysis/            analysis and strengthening scripts, plus the vamigrate CLI
src/vaml/            library: metrics, estimands, assembly, adapters, orchestration
scripts/             corpus builders, experiment runner, primary analysis
corpora/             frozen task sets (60 primary + 20 stress per pipeline)
prompts/             the eight research prompt templates, released in full
protocol/            pre-registration, freeze tooling, lock file, amendments
results/analysis/    primary analysis outputs
results/strengthening/  strengthening analysis outputs
results/run/         confirmatory call ledger (20,160 calls)
figures/             generated figures (PDF + PNG)
tests/               451 tests
docs/                CLI documentation, methods disclosures, install notes
data/raw/            NOT redistributed - see section 8
```

### Non-authoritative directories, retained for audit

| Directory | Status |
|---|---|
| `results/aborted_qc_run/` | **Quarantined** pre-confirmatory QC data (82 calls at the pre-Amendment-001 token ceiling). **Never used in any reported result.** Retained because Amendment 001 is disclosed in the methods and its ledger hash is test-verified. |
| `results/analysis_BUGGY_DISCARDED/` | Output of a superseded analysis pass containing a corrected defect (see §8 of `EXECUTION_REPORT.md`). **Never authoritative.** Retained only for auditability. |

**The authoritative analysis is the corrected frozen analysis in
`results/analysis/` and `results/strengthening/`.**

## 3. Environment

Python **3.11.14**. Dependencies are pinned in `requirements.lock.txt`.

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock.txt
```

The embedding model (`sentence-transformers/all-mpnet-base-v2`, revision
`e8c3b32edf5434bc2275fc9bab85f82640a19130`) is downloaded on first use and
cached. Pass `--embedding-revision` explicitly to keep runs offline.

## 4. Running the tests

```bash
pytest tests/ protocol/ -q
```

Expected: **451 passed, 1 skipped**. The skip is a public-release-only guard,
enabled with `PUBLIC_RELEASE=1`.

## 5. Reproducing the main analyses

See `REPRODUCE.md` for copy-paste commands. In summary:

```bash
python scripts/run_analysis.py --out results/analysis
python scripts/run_extended_analysis.py --out results/analysis
```

Both read `results/run/calls.jsonl` and make no model calls. The primary
analysis takes roughly 15 minutes; the extended analysis roughly 35.

## 6. Regenerating figures and tables

```bash
python analysis/tolerance_nonvacuity.py
python analysis/plot_tolerance_decision_curves.py
python analysis/migration_baseline_ablations.py
python analysis/single_run_oracle_instability.py
python analysis/evaluation_budget_study.py
python analysis/bootstrap_coverage_simulation.py     # ~3 h at full settings
```

Figures are written to `figures/`, tables to `results/strengthening/`.

## 7. The `vamigrate` CLI

A reference implementation of the paper's procedure over precomputed outputs.
It never invokes a model.

```bash
python analysis/vamigrate.py compare \
    --incumbent tests/fixtures/incumbent.jsonl \
    --candidate tests/fixtures/candidate.jsonl \
    --metric exact --tolerance 0.05
```

Full documentation: `docs/VAMIGRATE_CLI.md`.

## 8. Data that cannot be redistributed

### ContractNLI (Pipeline 2 source)

**Not included.** ContractNLI is CC BY 4.0 but distributed behind a
click-through Terms of Use acceptance; redistributing the source files here
would bypass that flow.

| | |
|---|---|
| Source | https://stanfordnlp.github.io/contract-nli/ |
| Citation | Koreeda & Manning, *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*, Findings of EMNLP 2021 |
| File used | `train.json` |
| Expected SHA-256 | `dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5` |
| Expected path | `data/raw/contractnli/train.json` |

A user who independently obtains it under its own terms can place it at that
path and rebuild the P2 corpus:

```bash
python scripts/validate_contractnli.py --source data/raw/contractnli/train.json
python scripts/build_p2_corpus.py     --source data/raw/contractnli/train.json
```

The build is deterministic under seed 20260803 and reproduces the frozen
corpus hashes. **This step is not required** to reproduce the analyses: the 80
selected cases, with gold labels and evidence spans, are already committed in
`corpora/pipeline2/`.

Upstream `LICENSE` and `TERMS` files shipped with the dataset are
intentionally excluded rather than re-published.

### Execution environment

The confirmatory grid ran against an internal model-serving managed execution path. That
managed execution path, its credentials and its client are **not** part of this artifact, and
no production prompt or production source is included. The persisted call
ledger is sufficient to reproduce every reported statistic.

## 9. Reproducibility notes

- All randomness is seeded at **20260803**.
- One model condition (`gemini-2.5-pro`) was a mutable alias and has since been
  withdrawn from new users by its provider; that condition cannot be
  re-verified against the public API. See `docs/METHODS_DISCLOSURES.md`.
- Post-freeze source changes to `src/vaml/adapters/shim.py` and
  `scripts/run_experiment.py` (commit `e30c78e`) are a documented mid-run
  auth-recovery fix, recorded in `EXECUTION_REPORT.md` §7.
- The confirmatory runs were executed through an internal corporate LLM
  managed execution path. The protocol, model map and execution reports therefore name that
  environment and its internal model identifiers (for example the incumbent
  condition `gpt-4o-2024-11-20`). These are retained deliberately as
  methodological disclosure: they record where the measurements came from and
  are required to interpret the provenance of the ledger. They are identifiers
  and environment names only. No proprietary prompt text, production source
  code, internal dataset or credential is included in this artifact, and a
  test guard (`tests/test_no_proprietary_content.py`) enforces that.
- the managed execution path adapter itself (`vaml.adapters.provider_route_A`) is **not** included: it is
  internal client code with no reviewer value. Consequently
  `scripts/smoke_test.py`, a live-API credential check that imports it, cannot
  run here, and the protocol lock lists a compiled `provider_route_A` `.pyc` that the
  archive does not ship. Neither affects any reported result: every analysis in
  this artifact reads the persisted ledger and makes no model calls.

## 10. Reports

| File | Contents |
|---|---|
| `EXECUTION_REPORT.md` | counts, provenance, hash verification, incidents |
| `RESULTS_REPORT.md` | all scientific findings |
| `REPLICATION_REPORT.md` | direct-provider replication subset |
| `ARTIFACT_MANIFEST.md` / `.json` | hashes, seeds, expected outputs |

## License

Code in this repository is released under the MIT License (`LICENSE`).
ContractNLI-derived content in `corpora/pipeline2/` remains under CC BY 4.0 and
is attributed to its authors.


## 11. Relationship to the private artifact, and what was removed

This is the **public mirror**, derived from the private research artifact at
scientific freeze `3652060`.

The confirmatory runs were executed through a managed execution path operated
by the author's employer. **Execution-infrastructure identifiers were removed
from this public artifact because they are not necessary to reproduce any
reported analysis:** every statistic here is recomputed from the persisted
ledger, and no analysis makes a model call. Where a provenance field is still
required, neutral terminology is used — for example `managed_execution_path`
for the execution environment and `provider_route_A` for an internal adapter
module.

Removed or neutralized, none of which affects a reported result:

- the corporate name, the internal execution-service name, internal
  adapter/module names, internal credential-tooling names, and internal
  transport/proxy product names
- the internal model-catalog **request id** for the incumbent condition, which
  carried a vendor-routing suffix. It is replaced throughout by the public
  model id `gpt-4o-2024-11-20`. This is a 1:1 substitution: the suffix was a
  routing marker only, the served snapshot was the public dated one, and the
  **canonical** id that every analysis actually keys off is unchanged
  (`protocol/canonical_model_map.json`)
- the compiled transport-helper binary, which was specific to that execution
  path
- personal filesystem paths and corporate-only operational metadata

**What was deliberately kept,** because it is scientifically necessary:
estimands and analysis code; synthetic Pipeline 1 inputs; the full call ledger
and all model outputs; ContractNLI *sampling metadata* (never the raw dataset,
see §8); public immutable model ids; all seeds; every figure and table; all
strengthening analyses; the `vamigrate` CLI; and the complete audit history,
including Amendment 001 and the analysis-bug quarantine.

`protocol/protocol_lock.json` records the consequence honestly: **all 16
task-corpus hashes verify unchanged**, while six infrastructure/source files no
longer match the frozen hashes because their docstrings and comments were
rewritten. Those rewrites are textual only.

A private record proving this artifact derives from freeze `3652060` is
retained by the author and is not published, because it enumerates the
identifiers this mirror exists to remove.

### No reproducibility was lost

Every reported statistic reproduces bit-for-bit from this public tree. Re-running
the confirmatory analysis regenerates `results/analysis/pairwise_results.json`
identical to the copy shipped here (`2195d0d414409db0...`).

Note for anyone comparing against the private artifact: that file's SHA-256
differs between the two (`4bfc7317e4a811cd...` privately). The difference is
entirely the model-id label — all **1,320** leaf values are identical except
**56** occurrences of the incumbent's id string, and **zero numeric values
change**. No statistic, interval or verdict differs. The one
capability that is genuinely unavailable here — re-running the original calls
through the original managed execution path — was already unavailable to any
external reader of the private artifact, and is not required to verify any
claim in the paper.
