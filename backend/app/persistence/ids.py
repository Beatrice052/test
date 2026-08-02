"""RFC 9562 UUIDv7-style identifiers for externally visible objects."""

import secrets
import time
import uuid


def uuid7() -> uuid.UUID:
    """Create a time-sortable UUIDv7 without relying on Python 3.14's uuid.uuid7."""

    timestamp_ms = time.time_ns() // 1_000_000
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return uuid.UUID(int=value)


def new_id(prefix: str) -> str:
    """Return a prefixed, sortable object identifier."""

    return f"{prefix}_{uuid7()}"
