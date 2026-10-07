#!/usr/bin/env bash
# P2.5 PK campaign attempt 2 — per-slot collector loop (supplement step 5). Every 300 s, run the idempotent
# `collect` for every slot that is not yet final (final = stopped_verified AND no UNAVAILABLE cell). A slot left
# `shutdown_unresolved` or with a failed fetch/export is simply collected again (fresh collect-<k> dir).
# Ends when all 9 slots are final. Run detached: setsid nohup bash <this file> &
cd /home/lenovo/projects/memory || exit 1
G=plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1
LOG=plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-campaign-launch/attempt-2/collect-loop.log
RUNNER=modal-runners/modal-m4-sgm-p2p5-pk-packed-campaign-slot-runner.py
SLOTS="learned-n32 oracle-n32 random_fixed-n32 single_cell-n32 learned-n16 random_fixed-n16 single_cell-n16 memory_off-n32 memory_off-n16"
FINAL='import json,sys
try: st=json.load(open(sys.argv[1]))
except Exception: sys.exit(1)
c=st.get("cells") or {}
sys.exit(0 if (st.get("final_shutdown") or {}).get("status")=="stopped_verified" and c and all(v.get("state")!="UNAVAILABLE" for v in c.values()) else 1)'
echo "$(date -u +%FT%TZ) loop start pid $$" >> "$LOG"
while true; do
  open=0
  for s in $SLOTS; do
    .venv/bin/python -c "$FINAL" "$G/$s/collect_status.json" && continue
    open=$((open + 1))
    M4_PK_SLOT=$s timeout 2400 .venv/bin/python "$RUNNER" collect >> "$LOG" 2>&1
    echo "$(date -u +%FT%TZ) $s collect rc=$?" >> "$LOG"
  done
  if [ "$open" -eq 0 ]; then echo "$(date -u +%FT%TZ) ALL 9 SLOTS FINAL" >> "$LOG"; break; fi
  sleep 300
done
