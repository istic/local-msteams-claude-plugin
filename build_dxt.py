#!/usr/bin/env python3
"""Build the teams-log.dxt Desktop Extension file."""
from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).parent
OUTPUT = ROOT / "teams-log.dxt"

INCLUDE = [
    "manifest.json",
    "pyproject.toml",
    "teams_log_mcp",
    "teams_log_export",
    "pylib/ccl_chromium_reader",
]

_SKIP_SUFFIXES = {".pyc"}
_SKIP_DIR_NAMES = {"__pycache__", ".git", ".egg-info"}


def _should_skip(path: pathlib.Path) -> bool:
    if path.suffix in _SKIP_SUFFIXES:
        return True
    return any(part in _SKIP_DIR_NAMES for part in path.parts)


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            path = ROOT / item
            if path.is_file():
                zf.write(path, item)
            elif path.is_dir():
                for f in sorted(path.rglob("*")):
                    if f.is_file() and not _should_skip(f):
                        zf.write(f, str(f.relative_to(ROOT)))
            else:
                print(f"Warning: {item!r} not found, skipping")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Built {OUTPUT.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
