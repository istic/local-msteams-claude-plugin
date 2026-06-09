#!/usr/bin/env python3
"""Build teams-log distribution archives."""
from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).parent
BUILD_DIR = ROOT / "build"

# Files included in both archives
_COMMON = [
    "pyproject.toml",
    "teams_log_mcp",
    "teams_log_export",
    "pylib/ccl_chromium_reader",
]

# Additional files per archive type
_MCPB_ONLY = ["manifest.json"]
_PLUGIN_ONLY = [".claude-plugin", ".mcp.json", "skills"]

_SKIP_SUFFIXES = {".pyc"}
_SKIP_DIR_NAMES = {"__pycache__", ".git", "build"}


def _should_skip(path: pathlib.Path) -> bool:
    if path.suffix in _SKIP_SUFFIXES:
        return True
    return any(
        part in _SKIP_DIR_NAMES or part.endswith(".egg-info")
        for part in path.parts
    )


def _build(output: pathlib.Path, include: list[str]) -> None:
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in include:
            path = ROOT / item
            if path.is_file():
                zf.write(path, item)
            elif path.is_dir():
                for f in sorted(path.rglob("*")):
                    if f.is_file() and not _should_skip(f):
                        zf.write(f, str(f.relative_to(ROOT)))
            else:
                print(f"Warning: {item!r} not found, skipping")
    size_kb = output.stat().st_size / 1024
    print(f"Built {output.name} ({size_kb:.1f} KB)")


def main() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    _build(BUILD_DIR / "teams-log.mcpb", _COMMON + _MCPB_ONLY)
    _build(BUILD_DIR / "teams-log.zip", _COMMON + _PLUGIN_ONLY)


if __name__ == "__main__":
    main()
