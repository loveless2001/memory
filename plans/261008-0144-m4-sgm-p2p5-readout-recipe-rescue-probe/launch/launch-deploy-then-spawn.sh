#!/usr/bin/env bash
# Readout probe PAID launch (codex 21813 clearance; user 21755 conditional go, cap $40.75; 4 TOTAL admitted starts;
# one immutable 31,946.2 s deadline). ONE deploy, then ONE spawn ONLY if the deploy exited 0. No retry of either:
# any failure is preserved as-is and reported. Every output and exit status is kept in this launch dir.
set -u
cd "$(dirname "$0")/../../.."
L=plans/261008-0144-m4-sgm-p2p5-readout-recipe-rescue-probe/launch
R=modal-runners/modal-m4-sgm-p2p5-readout-probe-slot-runner.py
utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "start_utc=$(utc)" > $L/02-deploy.exit.txt
.venv/bin/python -m modal deploy $R > $L/02-deploy.txt 2>&1
rc=$?
{ echo "EXIT_STATUS=$rc"; echo "end_utc=$(utc)"; } >> $L/02-deploy.exit.txt
.venv/bin/python -m modal app list --json > $L/03-app-list-after-deploy.json 2>&1
[ $rc -eq 0 ] || exit $rc

echo "start_utc=$(utc)" > $L/04-spawn.exit.txt
.venv/bin/python $R spawn > $L/04-spawn.txt 2>&1
rc=$?
{ echo "EXIT_STATUS=$rc"; echo "end_utc=$(utc)"; } >> $L/04-spawn.exit.txt

.venv/bin/python - > $L/05-dicts-after-spawn.json 2>&1 <<'EOF'
import json, time
import modal
out = {"read_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
for key, name in (("guard", "memsub-m4-sgm-p2p5-readout-probe-guard"),
                  ("admission", "memsub-m4-sgm-p2p5-readout-probe-admission")):
    try:
        out[key] = dict(modal.Dict.from_name(name).items())     # read-only: no create_if_missing
    except Exception as e:
        out[key] = f"unavailable: {e!r:.200}"
print(json.dumps(out, indent=2, default=str))
EOF
exit $rc
