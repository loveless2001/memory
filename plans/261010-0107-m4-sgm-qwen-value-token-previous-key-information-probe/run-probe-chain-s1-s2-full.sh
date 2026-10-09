#!/bin/bash
# Fail-stop controller for the previous-key information probe (proposal v0.4, codex 22408).
# S1 -> validate S1 receipt -> S2 -> validate S2 receipt -> admitted full wall -> FULL -> validate FULL receipt.
# Each stage: cgroup scope (4400M RAM / 1200M swap) + timeout --signal=KILL <wall>. Any failure stops the
# chain (no retry). Exit codes are written synchronously after each stage as <stage_dir>.exit receipts.
# Launch ONLY after the user's scoped go, detached:
#   setsid nohup bash plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe/run-probe-chain-s1-s2-full.sh > /dev/null 2>&1 < /dev/null &
set -u
cd /home/lenovo/projects/memory || exit 2
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
unset PKPROBE_FORBID_MODEL
D=plans/261010-0107-m4-sgm-qwen-value-token-previous-key-information-probe
PY=.venv/bin/python
RUN=scripts/sgm-p2p5-previous-key-probe-run-s1-s2-full.py
REC=scripts/sgm-p2p5-previous-key-probe-stage-receipts-and-admission-validation.py
LOG=$D/chain.log

say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
stop() { say "CHAIN STOPPED: $*"; echo "STOPPED: $*" > "$D/chain-status.txt"; exit 1; }
stage() {  # mode wall out [extra args...]
  local mode=$1 wall=$2 out=$3; shift 3
  say "start $mode wall=${wall}s out=$out"
  systemd-run --user --scope --quiet --unit="pkprobe-$mode-$(date +%s)" -p MemoryMax=4400M -p MemorySwapMax=1200M \
    timeout --signal=KILL "$wall" "$PY" "$RUN" --mode "$mode" --wall-s "$wall" --out "$out" "$@" > "$out.log" 2>&1
  local rc=$?
  echo "$rc" > "$out.exit"
  say "end $mode rc=$rc"
  return "$rc"
}

for p in s1-smoke s2-smoke probe-run-v1; do
  [ -e "$D/$p" ] || [ -e "$D/$p.exit" ] && stop "$p already exists (no reuse, no retry)"
done
echo "RUNNING" > "$D/chain-status.txt"
say "chain start head=$(git rev-parse HEAD)"

stage s1 1800 "$D/s1-smoke" || stop "s1 rc != 0"
"$PY" "$REC" --validate s1 --dir "$D/s1-smoke" >> "$LOG" 2>&1 || stop "s1 receipt invalid"
stage s2 2400 "$D/s2-smoke" || stop "s2 rc != 0"
"$PY" "$REC" --validate s2 --dir "$D/s2-smoke" >> "$LOG" 2>&1 || stop "s2 receipt invalid"
W=$("$PY" "$REC" --full-wall --s1 "$D/s1-smoke" --s2 "$D/s2-smoke" 2>> "$LOG") || stop "full wall not admitted"
say "admitted full wall ${W}s"
stage full "$W" "$D/probe-run-v1" --s1-dir "$D/s1-smoke" --s2-dir "$D/s2-smoke" || stop "full rc != 0"
"$PY" "$REC" --validate full --dir "$D/probe-run-v1" >> "$LOG" 2>&1 || stop "full receipt invalid"
say "CHAIN COMPLETE"
echo "COMPLETE" > "$D/chain-status.txt"
