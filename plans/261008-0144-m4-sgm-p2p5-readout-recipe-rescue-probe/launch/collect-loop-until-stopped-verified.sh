#!/usr/bin/env bash
# Readout probe collect loop: run the frozen idempotent `collect` every 10 min. While the call is pending, collect
# only polls and writes status. Once the call is terminal (or past deadline + grace) collect stops the app by its BOUND
# id, verifies zero tasks/containers, writes the status durably, then fetches evidence. The loop exits on the first
# collect that reports `final` (stop attempted), or on any collect error (exit != 0) so a human looks at it.
set -u
cd "$(dirname "$0")/../../.."
L=plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/launch
R=modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py
while true; do
  out=$(.venv/bin/python $R collect 2>&1)
  rc=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc $(echo "$out" | tail -1)" >> $L/08-collect-loop.log
  if [ $rc -ne 0 ]; then echo "$out" > $L/08-collect-error.txt; exit $rc; fi
  if echo "$out" | tail -1 | grep -q '"final": true'; then exit 0; fi
  sleep 600
done
