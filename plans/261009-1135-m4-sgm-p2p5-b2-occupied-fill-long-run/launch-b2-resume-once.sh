#!/usr/bin/env bash
# B2 RESUME v0.4 (start-2 from the update-750 checkpoint): read-only precheck -> `modal deploy` -> spawn ONE
# call (it runs WITHOUT this PC) -> local watcher that stops + verifies the deployed app when the call returns
# or at the resume deadline + 120 s (only while this PC is up; otherwise run cleanup-verify when back).
# Start ONCE, detached:  setsid nohup bash <this file> > /dev/null 2>&1 < /dev/null &
# Refuses on a dirty tracked tree or an existing output dir. Records HEAD, pid/pgid, every step's exit status.
set -u
cd "$(dirname "$0")/../.."
PY=/home/lenovo/projects/memory/.venv/bin/python        # the worktree has no venv of its own
P=plans/261009-1135-m4-sgm-p2p5-b2-occupied-fill-long-run
OUT=$P/b2-resume-v1
RN=modal-runners/modal-m4-sgm-p2p5-b2-occupied-fill-resume-runner.py
stamp() { echo "$1 $(date -u +%FT%T.%NZ)"; }
if [ -e "$OUT" ] || [ -e "$P/b2-resume-v1.launch.txt" ]; then echo "refusing: $OUT or its launch record exists"; exit 2; fi
DIRTY=$(git status --porcelain -- memsub scripts modal-runners "$P" plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen/inputs | wc -l)
if [ "$DIRTY" -ne 0 ]; then echo "refusing: dirty tracked tree ($DIRTY)" > "$P/b2-resume-v1.refused.txt"; exit 3; fi
{ echo "head $(git rev-parse HEAD)"; echo "branch $(git rev-parse --abbrev-ref HEAD)"; echo "start_utc $(date -u +%FT%T.%NZ)";
  echo "pid $$ pgid $(ps -o pgid= -p $$ | tr -d ' ') sid $(ps -o sid= -p $$ | tr -d ' ')"; } > "$P/b2-resume-v1.launch.txt"
timeout 120 "$PY" "$RN" precheck > "$P/b2-resume-v1.precheck.log" 2>&1
RC=$?; stamp "$RC" > "$P/b2-resume-v1.precheck-exit.txt"
if [ "$RC" -ne 0 ]; then exit 4; fi                       # nothing deployed, nothing spawned
timeout 600 "$PY" -m modal deploy "$RN" > "$P/b2-resume-v1.deploy.log" 2>&1
RC=$?; stamp "$RC" > "$P/b2-resume-v1.deploy-exit.txt"
if [ "$RC" -ne 0 ]; then exit 5; fi                       # no call spawned; stop any half-deployed app by hand
timeout 300 "$PY" "$RN" spawn-resume "$OUT" > "$P/b2-resume-v1.spawn.log" 2>&1
RC=$?; stamp "$RC" > "$P/b2-resume-v1.spawn-exit.txt"
if [ "$RC" -ne 0 ]; then                                  # fail closed: stop the deployed app now
  timeout --signal=KILL 330 "$PY" "$RN" cleanup-verify "$OUT" > "$P/b2-resume-v1.cleanup.log" 2>&1
  stamp "$?" > "$P/b2-resume-v1.cleanup-exit.txt"; exit 6
fi
timeout --signal=KILL 15600 "$PY" "$RN" watch "$OUT" > "$P/b2-resume-v1.watch.log" 2>&1   # RESUME_S + 120 + 300 + slack
stamp "$?" > "$P/b2-resume-v1.watch-exit.txt"
