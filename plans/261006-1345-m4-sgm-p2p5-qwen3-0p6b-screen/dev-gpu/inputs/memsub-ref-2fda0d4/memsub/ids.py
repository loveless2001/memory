"""ULID-style sortable identifiers with schema prefixes (mb_, th_, ckpt_, ...)."""

import os
import time

_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_B32[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_id(prefix: str) -> str:
    """Time-sortable id: 48-bit ms timestamp + 80 bits of randomness."""
    ts = _encode(int(time.time() * 1000), 10)
    rand_int = int.from_bytes(os.urandom(10), "big")
    return f"{prefix}_{ts}{_encode(rand_int, 16)}"


def new_thread_id() -> str:
    return new_id("th")


def new_block_id() -> str:
    return new_id("mb")


def new_checkpoint_id() -> str:
    return new_id("ckpt")


def new_span_id() -> str:
    return new_id("sp")
