"""Reuse the previously reviewed probes with acceptance assertions for the reported fixes."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'codex-261007-p2p5-pk-6a81005-progress-audit/probe-revised-boundaries.py'
source = OLD.read_text()
replacements = [
    ('6a81005820d4424401d1c99892093fc7ec6d6ae9', '8b2d9c1a05579f2ef6110f981a4553f948da9dbc'),
    ('Local independent review of 6a81005.', 'Local independent review of 8b2d9c1.'),
    ("fallback_lost_on_immediate_self_stop", "fallback_logged_before_immediate_self_stop"),
    ("assert p.returncode == 0 and not p.stdout and not p.stderr",
     "assert p.returncode == 0 and p.stdout and not p.stderr\n"
     "logged = json.loads(p.stdout)['m4_pk_control_tick']\n"
     "assert logged['self_stop_due'] is True and logged['outcomes'] == "
     "{'__unresolved__':['slot'],'__control__':'fallback due'}"),
    ("assert r['worker_crash']['descendant_still_running']", "assert not r['worker_crash']['descendant_still_running']"),
    ("assert guard['deadline_epoch']>latest and spawned", "assert guard['deadline_epoch']==latest and spawned"),
]
for before, after in replacements:
    assert source.count(before) == 1, before
    source = source.replace(before, after)
with (HERE / 'independent-regression-probes.py').open('x') as f:
    f.write(source)
print('Prepared immutable-source regression probes for 8b2d9c1.')
