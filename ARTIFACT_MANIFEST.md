# Artifact manifest

**Scientific freeze commit:** `3652060`  
**Packaging commit:** `ada9d16c14fa298d73bf21ac749b7b0768cc91cf`  
**Generated:** 2026-09-13T08:06:11.854457+00:00  
**Tests:** 451 passed, 1 skipped

Machine-readable form: `ARTIFACT_MANIFEST.json`.

## Environment

- Python **3.11.14**
- lock `requirements.lock.txt` sha256 `bc3287a7a0a983f1b428eb5ba296cb82...`
- embedding `sentence-transformers/all-mpnet-base-v2` @ `e8c3b32edf5434bc...`, cosine 0.8

## Seeds

- `global_random_seed` = 20260803
- `bootstrap_seed` = 20260803
- `corpus_build_seed` = 20260803
- `execution_order_seed` = 20260803
- `replication_subset_seed` = 20269804

## Design

| parameter | value |
|---|---|
| pipelines | 2 |
| primary_tasks_per_pipeline | 60 |
| stress_tasks_per_pipeline | 20 |
| incumbent_repetitions | 8 |
| candidate_repetitions | 5 |
| candidates | 4 |
| stages_per_run | 4 |
| total_runs | 5040 |
| total_calls | 20160 |
| bootstrap_replicates | 10000 |
| p2_declared_tolerance | 0.05 |
| p1_declared_tolerance | None |

## Corpus hashes

| file | sha256 |
|---|---|
| `corpora/pipeline1/p1_primary.jsonl` | `6215f2a99e5455bf06c1de3dd2f6482a77e66f7ffec2956942fa1f9c89d578a7` |
| `corpora/pipeline1/p1_stress.jsonl` | `bc6e5539d40acb25c57897a1fe48cbc3adaad8a8d9f4bfc043ac35c176e2a706` |
| `corpora/pipeline2/p2_primary.jsonl` | `53082a01241d248809021876dea1655d0834fec18ab4d035a9376470adc717f6` |
| `corpora/pipeline2/p2_stress.jsonl` | `f96006eebec93ca1ef64a46a4e0811eeeb381fcfab937e63be63a179546abb74` |

## Prompt hashes

| file | sha256 |
|---|---|
| `prompts/pipeline1/stage1_pr_signal.md` | `c890526ddb02c0d5ebdfb1f75548662f96f771f1906b87f39cbad07609448c05` |
| `prompts/pipeline1/stage2_review_signal.md` | `ab627f4fb57d14f9bdfba95be1bffd29aa21f1d6de20f040f475916d94a59838` |
| `prompts/pipeline1/stage3_synthesis.md` | `f9fecf027aec29cdb208eb360c95c85fc213001f4aec2ebfb3abe9a3c61970a1` |
| `prompts/pipeline1/stage4_deepen.md` | `8adf88a4e3d821f3ac0a73b0f66e373683a9825e264ca31ab2fe922f89687f14` |
| `prompts/pipeline2/stage1_extract_evidence.md` | `e507adf84dc969cd5bc1630a2e626e2a68713672af905cc0b26f68a707521e5c` |
| `prompts/pipeline2/stage2_assess_evidence.md` | `6bb0bc9c4acd5c4ce240cc002b14ff8b4236e346caacce1af0feff386c6b692c` |
| `prompts/pipeline2/stage3_classify.md` | `54b3d4875010e64e6761d71791d94be16c22d94cdb086cb5592dee043d7a3f7a` |
| `prompts/pipeline2/stage4_verify.md` | `fbad3d8bf79d739abd1bd7f1f111ae12ddb666a917f9f8d92e1d0971b8b39d62` |

## Protocol hashes

| file | sha256 |
|---|---|
| `protocol/PROTOCOL.md` | `a69780723c0dcc9e5aeefb6eb5b3e25053bacc8a2f6d306e2d804b3f869794ce` |
| `protocol/canonical_model_map.json` | `c72f788f31476c622367c962585a294d665cd241d8f353456c828c0782104203` |
| `protocol/protocol_lock.json` | `79daa80cb5c168845dbb948675f61dd575055e78d281b28ee698e35cb4d936f2` |
| `protocol/protocol_spec.json` | `de2ec678fe5e0db7c2ae6d18b09667db7d87963342504686ee6dee74d9461cea` |
| `protocol/replication_subset.json` | `4492fd6ddf620bea7c853081c78a9dc6a26366e57ba027ef5885397e3cc17aae` |

## Confirmatory ledger

| file | sha256 |
|---|---|
| `results/run/calls.jsonl` | `c47939ee14844755621fd4e83422636bbd009ab7fee4ae5dd91a7b2d4ffe39a9` |

## Primary analysis outputs

| file | sha256 |
|---|---|
| `results/analysis/execution_summary.json` | `70a3411bd05d80ae0da784751d9c3d890a2bc72dca26ca46d1eeb518a260d411` |
| `results/analysis/extended_analysis.json` | `b3d0ecb7ca293775d53c729bb841983d9b010e0da5ea706307a9cd212cb738b8` |
| `results/analysis/pairwise_results.json` | `2195d0d414409db0b32a3871547cc09e4aa8899b51eabb42c2e164395562ade8` |
| `results/analysis/replication_comparison.json` | `c3aeddd8a3013a2ac92506f51aa96ddbf7669d218e79b7b6cbd2941f18651b11` |

## Strengthening outputs

| file | sha256 |
|---|---|
| `results/strengthening/baseline_ablations.csv` | `13bb17ada8dce9085cc58394dd0ed08bdd6afee854195218bf7fd7326b4433f6` |
| `results/strengthening/bootstrap_coverage.csv` | `755d0a3a3def097eef0a38dfaaad8f1cc6438ff937fba2fb2bceca3197f6d2f0` |
| `results/strengthening/bootstrap_resolution_sensitivity.csv` | `89d1ccf9ca84c23d68a42ae332e84efd57462587debe3e958b8842cf90c4dd84` |
| `results/strengthening/contractnli_subset_representativeness.csv` | `d03ca7ff45084e98682e899c2b0dd668d3c1d11b3a2f84ee8fa0359cffd9b185` |
| `results/strengthening/evaluation_budget.csv` | `4ad74d40066bba482d67a81a4da6108e304b98003ef906bb3cb2205d680fa550` |
| `results/strengthening/invalid_output_sensitivity.csv` | `1eb48349bc1276f782c6b6bc5123ca171a2a24fc708e7c60fd972fe39765f48a` |
| `results/strengthening/p2_tolerance_transition_points.csv` | `421065eb4e15d2757af8a574c6f549211efc200a3067b941d108691f6afd064d` |
| `results/strengthening/simultaneous_inference.csv` | `305676bd85927388366f3cc210fa163ba79bc09c4e0c08204710f026b8aaa838` |
| `results/strengthening/single_run_oracle_instability.csv` | `fd029dbfe59cb850a17df63d37eeec99760a9ac5dc38f725ffa7d674abd1ae75` |
| `results/strengthening/tolerance_nonvacuity.csv` | `a4c1c4cbe14ead391bb6af4825da8f3f4fe68e1abfa5a8296dbe773341444ce8` |

## Non-authoritative directories

- **`results/aborted_qc_run/`** — Quarantined pre-confirmatory QC data: 82 calls made at the pre-Amendment-001 output ceiling. NEVER used in any reported result. Retained for audit; its ledger hash is test-verified.
- **`results/analysis_BUGGY_DISCARDED/`** — Output of a superseded analysis pass containing a corrected defect. NEVER authoritative. Retained only for auditability.

The authoritative analysis is results/analysis/ and results/strengthening/ at scientific freeze commit 3652060.

## Excluded from the release archive

- `data/raw/contractnli/*.json` — ContractNLI source files. CC BY 4.0 but distributed behind a click-through Terms of Use; not redistributed. Expected train.json SHA-256 dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5
- `data/raw/contractnli/{LICENSE,TERMS}` — Upstream dataset license files, intentionally not re-published.
- `.git/` — version-control history
- `__pycache__/, *.pyc` — interpreter caches
- `.venv/, venv/` — virtual environments
- `*.log, results/run/*.pre_*` — logs and ledger backups
- `.replication.env, .env, vaml.env` — credential files, never committed

## Post-freeze source changes

Commit `e30c78e` touching `src/vaml/adapters/shim.py`, `scripts/run_experiment.py`.

Documented mid-run auth-recovery fix after a host restart left the execution transport helper with stale credentials. Recorded in EXECUTION_REPORT.md section 7. Changes execution infrastructure only; no experimental condition, corpus, prompt or estimand was altered.

## Expected generated outputs

**Figures (14):** `baseline_ablations.pdf`, `baseline_ablations.png`, `bootstrap_coverage.pdf`, `bootstrap_coverage.png`, `evaluation_budget_repetitions.pdf`, `evaluation_budget_repetitions.png`, `evaluation_budget_tasks.pdf`, `evaluation_budget_tasks.png`, `p2_tolerance_decision_curves.pdf`, `p2_tolerance_decision_curves.png`, `single_run_oracle_instability.pdf`, `single_run_oracle_instability.png`, `tolerance_nonvacuity.pdf`, `tolerance_nonvacuity.png`

**Tables (10):** `baseline_ablations.csv`, `bootstrap_coverage.csv`, `bootstrap_resolution_sensitivity.csv`, `contractnli_subset_representativeness.csv`, `evaluation_budget.csv`, `invalid_output_sensitivity.csv`, `p2_tolerance_transition_points.csv`, `simultaneous_inference.csv`, `single_run_oracle_instability.csv`, `tolerance_nonvacuity.csv`

