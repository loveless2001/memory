"""Immutable binding for the private MergeCert Q1 registration.

Step 1a replaces the pending sentinel with the reviewed registration's
literal SHA-256.  Campaign consumers import this one value so a supplied
registration can never authorize itself.
"""

import hashlib
import json

Q1_REGISTRATION_PENDING = "PENDING_CPU_EXTRACTION"
Q1_REGISTRATION_SHA256 = Q1_REGISTRATION_PENDING
Q1_REGISTRATION_LOCAL_PATH = (
    "plans/260728-mergecert-q1/q1-registration.json"
)
Q1_REGISTRATION_REMOTE_PATH = (
    "/artifacts/mergecert-q1/q1-registration.json"
)


def canonical_q1_registration_bytes(registration: dict) -> bytes:
    return (
        json.dumps(registration, indent=1, allow_nan=False) + "\n"
    ).encode()


def canonical_q1_registration_sha256(registration: dict) -> str:
    return hashlib.sha256(
        canonical_q1_registration_bytes(registration)
    ).hexdigest()


def require_q1_registration_binding() -> str:
    if Q1_REGISTRATION_SHA256 == Q1_REGISTRATION_PENDING:
        raise ValueError(
            "Q1 finalized registration binding is pending CPU extraction "
            "and independent review"
        )
    if (
        not isinstance(Q1_REGISTRATION_SHA256, str)
        or len(Q1_REGISTRATION_SHA256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in Q1_REGISTRATION_SHA256
        )
    ):
        raise ValueError("Q1 finalized registration SHA-256 binding is invalid")
    return Q1_REGISTRATION_SHA256
