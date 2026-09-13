# The execution transport helper

## Why it exists

A plain HTTPS client — Python `urllib`, `http.client`, and `curl` all tested —
is rejected at the managed transport layer with an **empty-bodied 401 from
the transport layer**, while the production Go client authenticates successfully with
*identical* credentials, IAM ticket, headers, and endpoint, seconds apart.

Ruled out during diagnosis: credential mismatch, missing `TEST` /
`x-skip-risk-screening` / `x-use-case` headers, User-Agent filtering, header
capitalisation, endpoint path variants, and a local auth proxy. The rejection
happens before the request reaches the LLM service, so the difference is
a transport-layer workload identity that a standalone HTTPS client cannot present.

Rather than reverse-engineer that, the harness delegates transport to a small
Go binary built against the known-working client.

## What it is

`cmd/transport-helper` **in the service module** (not vendored here — it imports
internal packages, and copying it would pull production source into this
research repository).

Line-delimited JSON over stdin/stdout, one response per request, in order:

```json
{"custom_id":"…","model":"…","system_prompt":"…","user_prompt":"…","max_tokens":2048}
{"custom_id":"…","ok":true,"returned_model_id":"…","text":"…","prompt_tokens":25,…}
```

The client's verbose debug output is redirected to stderr inside the transport helper so
stdout carries only protocol JSON. Credentials are loaded by the transport helper itself
and never cross the boundary.

## Build

```bash
cd "$SERVICE_MODULE_DIR"          # the module containing cmd/transport-helper
go build -o "$VAML_REPO/bin/transport-helper" ./cmd/transport-helper
```

Credentials are supplied via `VAML_ENV_FILE`, pointing at a local env file
outside this repository.

`bin/` is gitignored — the binary is 36 MB and rebuildable from source.

## Scope

**Execution infrastructure only.** No experimental condition changes: corpora,
prompts, model ids, repetition counts, estimands, tolerances, retry/exclusion
rules and the randomized schedule are untouched. The protocol hash advances
because `src/` and `scripts/` change; corpus and prompt hashes are unchanged and
that is asserted at re-freeze.

## Payload note

the managed execution path rejects OpenAI-style `model_parameters` on this endpoint
(`"Unrecognized request argument supplied: model_parameters"`), so the transport helper
sends `max_tokens` (and any temperature/top_p) at the top level for all models.
The frozen decoding condition is unchanged: provider-default sampling with an
explicit `max_tokens`.

## Running the experiment

```bash
export VAML_ENV_FILE=/path/to/your/.env          # credentials, outside this repo
export VAML_PYTHON=/path/to/venv/bin/python      # interpreter with deps

./scripts/run_control.sh start     # launch or resume
./scripts/run_control.sh status    # operational QC
./scripts/run_control.sh stop      # safe to power off after this
```

The run is checkpointed: each completed call is flushed to
`results/run/calls.jsonl` immediately, so stopping loses at most the single
call in flight. Resuming skips everything already recorded.
