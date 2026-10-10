#!/bin/bash
# Per-file pytest for mvp (base) and trial merge (cand): each file in its own capped scope; junit per file.
S=/tmp/claude-1000/-home-lenovo-projects/39c47b94-d052-4208-8b37-4c7ca18c55b5/scratchpad/merge-check
PY=/home/lenovo/projects/memory/.venv/bin/python
for t in base cand; do
  cd $S/$t || exit 2
  mkdir -p $S/pf-$t
  for f in tests/test_*.py; do
    n=$(basename $f .py)
    env PKPROBE_FORBID_MODEL=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODAL_SERVER_URL=http://127.0.0.1:9 \
        MODAL_TOKEN_ID=ak-invalid MODAL_TOKEN_SECRET=as-invalid \
      systemd-run --user --scope --quiet -p MemoryMax=3500M -p MemorySwapMax=0 \
      timeout --signal=KILL 900 $PY -m pytest $f -q -p no:cacheprovider --basetemp $S/pf-$t/bt-$n \
        --junitxml $S/pf-$t/$n.xml > $S/pf-$t/$n.log 2>&1
    echo "$n $?" >> $S/pf-$t.status
    rm -rf $S/pf-$t/bt-$n
  done
done
echo DONE >> $S/perfile.status
