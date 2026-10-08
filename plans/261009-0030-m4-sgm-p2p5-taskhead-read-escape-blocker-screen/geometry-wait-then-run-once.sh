#!/usr/bin/env bash
# Stage A geometry pass (codex 22056 clearance): wait for the smollm controller (PID given) to exit, then
# launch the cleared diagnosis ONCE only if a fresh nvidia-smi shows no compute apps and < 300 MiB used.
# If the GPU is still busy, record it and DO NOT launch (no retry, no CPU fallback).
#   setsid nohup bash <this file> <smollm-controller-pid> > /dev/null 2>&1 < /dev/null &
set -u
cd "$(dirname "$0")/../.."
P=plans/261009-0030-m4-sgm-p2p5-taskhead-read-escape-blocker-screen
WAIT_PID=$1
if [ -e "$P/geometry-run-v1" ] || [ -e "$P/geometry-run-v1.gate.txt" ]; then echo "refusing: already launched/gated"; exit 2; fi
echo "waiting for pid $WAIT_PID from $(date -u +%FT%TZ) (waiter pid $$)" > "$P/geometry-run-v1.wait.txt"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done
sleep 20
echo "controller $WAIT_PID gone at $(date -u +%FT%TZ)" > "$P/geometry-run-v1.gate.txt"
if ! APP_ROWS=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>> "$P/geometry-run-v1.gate.txt"); then
  echo "GPU compute-app query failed: NOT launched" >> "$P/geometry-run-v1.gate.txt"; exit 4
fi
if ! MEMORY_ROWS=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>> "$P/geometry-run-v1.gate.txt"); then
  echo "GPU memory query failed: NOT launched" >> "$P/geometry-run-v1.gate.txt"; exit 4
fi
APPS=0
while IFS= read -r APP_ROW; do
  if [[ "$APP_ROW" =~ ^[[:space:]]*$ ]]; then continue; fi
  if ! [[ "$APP_ROW" =~ ^[[:space:]]*[0-9]+[[:space:]]*$ ]]; then
    echo "GPU compute-app query malformed: NOT launched" >> "$P/geometry-run-v1.gate.txt"; exit 4
  fi
  APPS=$((APPS + 1))
done <<< "$APP_ROWS"
if ! [[ "$MEMORY_ROWS" =~ ^[[:space:]]*[0-9]+[[:space:]]*$ ]]; then
  echo "GPU memory query malformed: NOT launched" >> "$P/geometry-run-v1.gate.txt"; exit 4
fi
MEM=${MEMORY_ROWS//[[:space:]]/}
echo "compute_apps $APPS memory_used_mib $MEM" >> "$P/geometry-run-v1.gate.txt"
if [ "$APPS" -ne 0 ] || [ "$MEM" -ge 300 ]; then echo "GPU busy: NOT launched" >> "$P/geometry-run-v1.gate.txt"; exit 3; fi
echo "GPU free: launching at $(date -u +%FT%TZ) from HEAD $(git rev-parse HEAD)" >> "$P/geometry-run-v1.gate.txt"
timeout --signal=KILL 3600 .venv-gpu/bin/python scripts/sgm-p2p5-taskhead-dead-start-address-diagnosis.py \
    --index "$P/geometry-index-v1.json" --out "$P/geometry-run-v1" > "$P/geometry-run-v1.console.log" 2>&1
echo $? > "$P/geometry-run-v1.exit.txt"
{ echo "post-run $(date -u +%FT%TZ)"; ps -eo pid,args | grep -c "[s]gm-p2p5-taskhead-dead-start-address-diagnosis.py --index $P"; \
  nvidia-smi --query-gpu=memory.used --format=csv,noheader; } > "$P/geometry-run-v1.cleanup.txt"
