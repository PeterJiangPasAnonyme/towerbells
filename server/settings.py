"""Runtime settings from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ADMIN_ENABLED = _env_bool("TOWERBELLS_ADMIN_ENABLED", default=True)

_db_path = os.environ.get("TOWERBELLS_DB_PATH", "data/towerbells.db").strip()
DB_PATH = Path(_db_path)
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
