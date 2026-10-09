#!/usr/bin/env bash
# B1 single launch: ONE bounded ephemeral `modal run`, then cleanup-verify. Runs from the
# m4-sgm-occupied-fill-v1 worktree (the runner refuses unless local memsub == the bound sha).
# Start ONCE, detached:  setsid nohup bash <this file> > /dev/null 2>&1 < /dev/null &
# Refuses on a dirty tracked tree or an existing output dir. Records HEAD, pid/pgid, console, exit
# statuses, and the cleanup verdict beside the output dir.
set -u
cd "$(dirname "$0")/../.."
PY=/home/lenovo/projects/memory/.venv/bin/python        # the worktree has no venv of its own
P=plans/261009-1040-m4-sgm-p2p5-b1-occupied-fill-retention-screen
OUT=$P/b1-run-v1
RN=modal-runners/modal-m4-sgm-p2p5-b1-occupied-fill-retention-screen-runner.py
if [ -e "$OUT" ] || [ -e "$P/b1-run-v1.launch.txt" ]; then echo "refusing: $OUT or its launch record exists"; exit 2; fi
DIRTY=$(git status --porcelain -- memsub scripts modal-runners "$P" plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs | wc -l)
if [ "$DIRTY" -ne 0 ]; then echo "refusing: dirty tracked tree ($DIRTY)" > "$P/b1-run-v1.refused.txt"; exit 3; fi
{ echo "head $(git rev-parse HEAD)"; echo "branch $(git rev-parse --abbrev-ref HEAD)"; echo "start_utc $(date -u +%FT%T.%NZ)";
  echo "pid $$ pgid $(ps -o pgid= -p $$ | tr -d ' ') sid $(ps -o sid= -p $$ | tr -d ' ')";
  echo "argv timeout --signal=TERM --kill-after=30s 2610 $PY -m modal run $RN --out $OUT"; } > "$P/b1-run-v1.launch.txt"
timeout --signal=TERM --kill-after=30s 2610 "$PY" -m modal run "$RN" --out "$OUT" > "$P/b1-run-v1.console.log" 2>&1
echo "$? $(date -u +%FT%T.%NZ)" > "$P/b1-run-v1.exit.txt"
"$PY" "$RN" cleanup-verify "$OUT" > "$P/b1-run-v1.cleanup.log" 2>&1
echo "$? $(date -u +%FT%T.%NZ)" > "$P/b1-run-v1.cleanup-exit.txt"
