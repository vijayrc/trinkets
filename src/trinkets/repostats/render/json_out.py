"""JSON rendering, for piping the report into other tools."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from trinkets.repostats.models import RepoReport


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def render_json(report: RepoReport, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, default=_default, ensure_ascii=False)
