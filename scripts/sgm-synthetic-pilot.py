"""Run one M4-SGM P2 synthetic pilot locally (CPU).

    uv run python scripts/sgm-synthetic-pilot.py --config configs/m4_sgm_tiny.json \
        --arm oracle --n-bindings 16 --steps 300 --out plans/<dir>/runs/<run-id>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memsub.sgm.synthetic_pilot import PilotConfig  # noqa: E402
from memsub.sgm.synthetic_pilot_run import run_pilot  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/m4_sgm_tiny.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--arm"); ap.add_argument("--readout")
    ap.add_argument("--n-bindings", type=int); ap.add_argument("--steps", type=int)
    ap.add_argument("--seed", type=int); ap.add_argument("--sgm", type=json.loads)
    args = ap.parse_args()
    raw = {k: v for k, v in json.loads(args.config.read_text()).items() if not k.startswith("_")}
    for key in ("arm", "readout", "n_bindings", "steps", "seed", "sgm"):
        if getattr(args, key) is not None:
            raw[key] = getattr(args, key)
    metrics = run_pilot(PilotConfig(**raw), args.out)
    print(json.dumps({k: (v["accuracy"] if v else None) for k, v in metrics["final"].items()}, indent=2))


if __name__ == "__main__":
    main()
