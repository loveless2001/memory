#!/usr/bin/env bash
# Stage A single launch (proposal v0.4): ONE bounded ephemeral `modal run`, then cleanup-verify.
# Start ONCE, detached:  setsid nohup bash <this file> > /dev/null 2>&1 < /dev/null &
# Refuses on a dirty tracked tree or an existing output dir. Records HEAD, pid/pgid, console, exit
# statuses, and the cleanup verdict beside the output dir.
set -u
cd "$(dirname "$0")/../.."
P=plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen
OUT=$P/stage-a-run-v1
RN=modal-runners/modal-m4-sgm-p2p5-stage-a-read-escape-blocker-runner.py
if [ -e "$OUT" ] || [ -e "$P/stage-a-run-v1.launch.txt" ]; then echo "refusing: $OUT or its launch record exists"; exit 2; fi
DIRTY=$(git status --porcelain -- memsub scripts modal-runners "$P/inputs" | wc -l)
if [ "$DIRTY" -ne 0 ]; then echo "refusing: dirty tracked tree ($DIRTY)" > "$P/stage-a-run-v1.refused.txt"; exit 3; fi
{ echo "head $(git rev-parse HEAD)"; echo "start_utc $(date -u +%FT%T.%NZ)"; echo "pid $$ pgid $(ps -o pgid= -p $$ | tr -d ' ') sid $(ps -o sid= -p $$ | tr -d ' ')";
  echo "argv timeout --signal=TERM --kill-after=30s 4710 .venv/bin/python -m modal run $RN --out $OUT"; } > "$P/stage-a-run-v1.launch.txt"
timeout --signal=TERM --kill-after=30s 4710 .venv/bin/python -m modal run "$RN" --out "$OUT" > "$P/stage-a-run-v1.console.log" 2>&1
echo "$? $(date -u +%FT%T.%NZ)" > "$P/stage-a-run-v1.exit.txt"
.venv/bin/python "$RN" cleanup-verify "$OUT" > "$P/stage-a-run-v1.cleanup.log" 2>&1
echo "$? $(date -u +%FT%T.%NZ)" > "$P/stage-a-run-v1.cleanup-exit.txt"
