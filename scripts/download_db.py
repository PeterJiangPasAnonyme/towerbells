#!/usr/bin/env python3
"""Download towerbells.db for deployment builds."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "towerbells.db"


def main() -> int:
    if DEST.exists() and not os.environ.get("TOWERBELLS_DB_URL", "").strip():
        print(f"Using existing {DEST}")
        return 0

    url = os.environ.get("TOWERBELLS_DB_URL", "").strip()
    if not url:
        print(
            "Missing TOWERBELLS_DB_URL. Upload towerbells.db to a GitHub Release "
            "and set that asset URL on Render.",
            file=sys.stderr,
        )
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading database from {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "towerbells-deploy/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    if len(data) < 1024:
        print("Downloaded file looks too small to be a valid SQLite database.", file=sys.stderr)
        return 1

    DEST.write_bytes(data)
    print(f"Saved {len(data):,} bytes to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
