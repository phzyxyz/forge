"""Identifiers that do not scan a table or collide under concurrency."""

from __future__ import annotations

import os
import time


def uuid7() -> str:
    """Return a UUID version 7 string.

    Used for refresh-token families. It does not replace integer user ids.

    Layout from RFC 9562, 16 bytes:

    - bytes 0–5: Unix time in milliseconds (48 bits), so ids sort by time
    - high 4 bits of byte 6: version number 7
    - high 2 bits of byte 8: the RFC variant bits ``10``
    - every other bit: random
    """
    timestamp_milliseconds = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    value = bytearray(os.urandom(16))
    value[0:6] = timestamp_milliseconds.to_bytes(6, "big")
    value[6] = (value[6] & 0x0F) | 0x70
    value[8] = (value[8] & 0x3F) | 0x80

    hexadecimal = value.hex()
    return (
        f"{hexadecimal[0:8]}-{hexadecimal[8:12]}-{hexadecimal[12:16]}-"
        f"{hexadecimal[16:20]}-{hexadecimal[20:32]}"
    )
