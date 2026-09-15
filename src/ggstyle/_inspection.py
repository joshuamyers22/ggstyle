"""JSON-safe inspection helpers shared by public summary and plan objects."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from enum import Enum
from typing import Any

from cycler import Cycler


def json_safe(value: Any) -> object:
    """Return a deterministic JSON-compatible description of ``value``."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((json_safe(item) for item in value), key=repr)
    if isinstance(value, Cycler):
        return json_safe(value.by_key())
    value_type = type(value)
    return f"<{value_type.__module__}.{value_type.__qualname__}>"


def describe(payload: Mapping[str, object]) -> str:
    """Render one inspection payload as stable, strict JSON."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
