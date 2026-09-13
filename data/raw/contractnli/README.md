# ContractNLI raw data — place the downloaded files here

**This directory is gitignored. Its contents are never committed.**

## Why

ContractNLI is CC BY 4.0, but the official distribution is behind a
click-through Terms of Use acceptance. Committing the source files here would
redistribute them outside that flow. Only *derived* artifacts — selected task
ids, gold labels, evidence spans for the 80 chosen cases, hashes and manifests —
are committed, and those live in `corpora/pipeline2/`.

No third-party mirror is used. No synthetic substitute is used for the real
experiment.

## What to place here

Download from the official source after accepting the ToU:

  https://stanfordnlp.github.io/contract-nli/

Expected file (any one of these is enough to build the corpus):

```
data/raw/contractnli/train.json
data/raw/contractnli/dev.json      # optional
data/raw/contractnli/test.json     # optional
```

## Then run

```bash
python scripts/validate_contractnli.py --source data/raw/contractnli/train.json
python scripts/build_p2_corpus.py     --source data/raw/contractnli/train.json
pytest tests/ -q
python scripts/dry_run.py --out results/dry_run
```

The build is deterministic under seed 20260803: the same input file always
yields the same 60 primary and 20 stress cases.
