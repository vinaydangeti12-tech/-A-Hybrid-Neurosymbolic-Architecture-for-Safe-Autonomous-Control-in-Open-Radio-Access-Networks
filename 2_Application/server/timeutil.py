"""Small time helper for the TRACE_v2 server.

`datetime.utcnow()` is deprecated from Python 3.12 (it returns a naive datetime
and is scheduled for removal). This helper computes a timezone-aware UTC instant
and drops the tzinfo, so it returns the *exact same* naive-ISO string the rest of
the code (and the React frontend's `new Date(...)`) already expects — no format
change, no deprecation warning.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC 'now' — a drop-in for the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
