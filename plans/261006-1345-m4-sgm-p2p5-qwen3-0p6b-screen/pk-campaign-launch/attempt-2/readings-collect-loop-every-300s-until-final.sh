#!/usr/bin/env bash
# P2.5 PK readings (post-hoc amendment a17cd40): every 300 s run the idempotent readings `collect` until the call is
# terminal, the app is stopped_verified and the volume evidence fetched completely. Run detached:
#   setsid nohup bash <this file> > /dev/null 2>&1 &
cd /home/lenovo/projects/memory || exit 1
ST=plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/p2p5-qwen3-0p6b-screen-v1/readings/collect_status.json
LOG=plans/261006-1345-m4-sgm-p2p5-qwen3-0p6b-screen/pk-campaign-launch/attempt-2/readings-collect-loop.log
RUNNER=modal-runners/modal-m4-sgm-p2p5-pk-campaign-readings-runner.py
FINAL='import json,sys
try: st=json.load(open(sys.argv[1]))
except Exception: sys.exit(1)
sys.exit(0 if (st.get("final_shutdown") or {}).get("status")=="stopped_verified" and st.get("evidence_complete") is True else 1)'
echo "$(date -u +%FT%TZ) loop start pid $$" >> "$LOG"
while true; do
  timeout 2400 .venv/bin/python "$RUNNER" collect >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) readings collect rc=$? poll=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("poll"))' "$ST" 2>/dev/null)" >> "$LOG"
  if .venv/bin/python -c "$FINAL" "$ST"; then echo "$(date -u +%FT%TZ) READINGS FINAL" >> "$LOG"; break; fi
  sleep 300
done
