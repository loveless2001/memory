"""Disposable CPU-only probe: exception right after Watchdog arming must not leave the sleeper alive."""
import importlib.util, sys
from pathlib import Path
import torch
ROOT = Path("/home/lenovo/projects/memory")
spec = importlib.util.spec_from_file_location("prof", ROOT / "scripts" / "sgm-p2p5-local-gpu-timing-profile.py")
prof = importlib.util.module_from_spec(spec); spec.loader.exec_module(prof)
prof.WALL_LIMIT_S = 777                                 # distinctive sleeper duration for the pgrep check
torch.cuda.is_available = lambda: True                  # pass the CUDA gate without a GPU
def boom(*_a, **_k): raise RuntimeError("injected setup failure after watchdog arming")
prof.source_tree_sha256 = boom
sys.argv = ["x", "--out", sys.argv[1]]
prof.main()
