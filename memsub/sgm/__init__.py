"""M4-SGM: Sparse Growing Memory research backend (see M4-SGM.md).

Research-only. Nothing here is wired into a default deployment path; the
session API lives in `memsub.sgm.backend`, the frozen-backbone runtime in
`memsub.runtime.sgm_model_runtime`.
"""

from .config import SGMConfig

__all__ = ["SGMConfig"]
