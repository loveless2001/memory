#!/bin/bash
# Wrapper: run the F4 analysis half (detached, unbuffered) — avoids re-typing
# the interpreter path on the command line.
cd /home/lenovo/projects/memory || exit 1
PY="$PWD/.venv/bin/python3"
"$PY" -u -c "
import warnings; warnings.filterwarnings('ignore')
src=open('plans/260719-0105-followup2-f4f5/analyze-followup2-f4-f5.py').read().split('if __name__')[0]
g={}; exec(compile(src,'m','exec'),g)
g['run_f4']()
"
