"""Exception taxonomy for the memory substrate.

Fail-closed semantics: redaction and compatibility violations must raise
before any cache-grade artifact is touched (spec 4.6, 19.x; BUILD.md GT2/GT3/GT5).
"""


class MemsubError(Exception):
    """Base class for all substrate errors."""


class CompatibilityError(MemsubError):
    """compatibility_fingerprint mismatch: artifact may never be loaded as live
    context (spec 4.6 - hard fail, all-or-nothing)."""


class SinkEvictionError(MemsubError):
    """A compaction plan attempted to evict pinned attention-sink positions
    (spec 13.2). Raised before the cache is touched (GT2)."""


class RedactionError(MemsubError):
    """Read of a redacted or redaction-invalidated artifact. Fails closed (GT5)."""


class IntegrityError(MemsubError):
    """Checksum mismatch on a stored artifact."""


class HydrationError(MemsubError):
    """Checkpoint hydration failed for a non-compatibility reason (missing
    pages, corrupt page table). Resume must fall back to the substrate."""
