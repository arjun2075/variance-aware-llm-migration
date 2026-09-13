#!/usr/bin/env bash
# Pause / resume / status for the confirmatory run.
#
# The run is CHECKPOINTED: every completed call is appended to
# results/run/calls.jsonl and flushed immediately. Stopping the process — or
# shutting the laptop down entirely — loses at most the one call in flight.
# Restarting skips everything already recorded and continues where it left off.
#
#   ./scripts/run_control.sh stop     # safe to shut down after this
#   ./scripts/run_control.sh start    # resume from the ledger
#   ./scripts/run_control.sh status
set -euo pipefail
cd "$(dirname "$0")/.."

PIDFILE=results/run/runner.pid
LEDGER=results/run/calls.jsonl
# Both are environment-supplied so no local or internal path is committed.
#   VAML_PYTHON   - interpreter with the analysis deps installed
#   VAML_ENV_FILE - credentials file, outside this repository
# Auto-load local machine paths if present (gitignored).
[ -f vaml.env ] && . ./vaml.env

PY="${VAML_PYTHON:-python3}"
if [ -z "${VAML_ENV_FILE:-}" ]; then
  echo "VAML_ENV_FILE is not set; export it to point at your credentials file" >&2
  exit 2
fi
export VAML_ENV_FILE

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "${1:-status}" in
  stop)
    if running; then
      PID=$(cat "$PIDFILE")
      # SIGTERM lets the current call finish writing its ledger line.
      kill -TERM "$PID" 2>/dev/null || true
      for _ in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
      kill -0 "$PID" 2>/dev/null && kill -KILL "$PID" 2>/dev/null || true
      rm -f "$PIDFILE"
      echo "stopped. $(wc -l < "$LEDGER" | tr -d ' ') calls recorded and flushed."
      echo "safe to shut down; run '$0 start' to resume."
    else
      echo "not running. $( [ -f "$LEDGER" ] && wc -l < "$LEDGER" | tr -d ' ' || echo 0) calls recorded."
    fi
    ;;
  start)
    if running; then echo "already running (pid $(cat "$PIDFILE"))"; exit 0; fi
    mkdir -p results/run
    nohup "$PY" scripts/run_experiment.py --out results/run \
      >> results/run/runner.log 2>&1 &
    echo $! > "$PIDFILE"
    echo "resumed as pid $(cat "$PIDFILE")"
    sleep 3
    grep -E "^resuming" results/run/runner.log | tail -1 || true
    ;;
  status)
    if running; then echo "RUNNING (pid $(cat "$PIDFILE"))"; else echo "STOPPED"; fi
    "$PY" scripts/qc_watch.py || true
    ;;
  *) echo "usage: $0 {start|stop|status}"; exit 2 ;;
esac
