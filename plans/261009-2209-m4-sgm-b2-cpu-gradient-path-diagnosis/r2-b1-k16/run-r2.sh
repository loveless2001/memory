#!/bin/bash
# r2 retry of the B2 CPU gradient-path diagnosis after the r1 OOM: B=1, K=16, one process per condition,
# each inside a systemd user scope with a cgroup memory cap so an overflow kills only the probe.
cd /home/lenovo/projects/memory-occupied-fill-v1-worktree || exit 2
O=plans/261009-2209-m4-sgm-b2-cpu-gradient-path-diagnosis/r2-b1-k16
F=scripts/sgm-p2p5-b2-cpu-task-gradient-path-and-retrieval-geometry-diagnosis.py
for c in init final oracle; do
  echo "$c start $(date -u +%FT%TZ)" >> $O/exits.txt
  systemd-run --user --scope --quiet --unit=m4-b2-cpu-probe-r2-$c -p MemoryMax=4400M -p MemorySwapMax=1200M \
    /usr/bin/time -v /home/lenovo/projects/memory/.venv/bin/python $F --out $O --conditions $c --batches 16 --batch-size 1 \
    > $O/$c.stdout.txt 2> $O/$c.stderr.txt
  echo "$c exit $? $(date -u +%FT%TZ)" >> $O/exits.txt
done
echo "ALL DONE $(date -u +%FT%TZ)" >> $O/exits.txt
