# Installing the real ContractNLI dataset

Pipeline 2 currently holds **synthetic fixtures**, which exist only so the
mocked orchestration could be rehearsed. They are **not** valid for the
confirmatory run, and `scripts/check_launch_readiness.py` refuses to pass while
they are in place.

## Steps

1. Accept the Terms of Use and download from the official source:
   <https://stanfordnlp.github.io/contract-nli/>
   No third-party mirror. No substitute.

2. Place the file (gitignored — never committed):
   ```
   data/raw/contractnli/train.json
   ```

3. Validate, rebuild, retest, re-freeze:
   ```bash
   python scripts/validate_contractnli.py --source data/raw/contractnli/train.json
   python scripts/build_p2_corpus.py     --source data/raw/contractnli/train.json
   pytest tests/ protocol/ -q
   python scripts/dry_run.py --out results/dry_run
   git add -A && git commit -m "Rebuild P2 corpus from real ContractNLI"
   python protocol/freeze_protocol.py freeze \
     --protocol protocol/PROTOCOL.md --spec protocol/protocol_spec.json \
     --corpus corpora --corpus prompts --code src --code scripts \
     --out protocol/protocol_lock.json
   python scripts/check_launch_readiness.py
   ```

## What the validator checks

Hard failures (exit 1–2): unparseable or truncated JSON; unrecognised structure;
fewer than 100 documents (80 distinct are needed for 60 primary + 20 stress);
duplicate document ids; invalid gold labels; out-of-range evidence-span indices;
fewer than 20 annotations for any label.

Soft observations: hypothesis count ≠ 17, document count > 607, bare-list top
level. These are recorded, not fatal.

## What gets committed

Committed: the 80 selected cases in `corpora/pipeline2/*.jsonl` (with gold
labels and spans, for scoring), the corpus report with hashes, and the
validation report including the source file's SHA-256.

Never committed: the ContractNLI source files themselves.

## Determinism

Seed 20260803. The same source file always yields the same 60 primary and 20
stress cases, sampled at the **document** level — one instance per document,
because the 17 shared hypotheses make doc×hypothesis pairs correlated.

## Gold handling

Gold labels and spans are stored for scoring only. `inference_view()` strips
every gold field before a record reaches a prompt; `tests/test_corpora.py`
asserts this, and the dry run re-checks every rendered prompt.
