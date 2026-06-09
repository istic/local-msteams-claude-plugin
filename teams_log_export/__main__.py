"""CLI entry point for teams-log-export."""

import argparse
import os
import pathlib
import sys

from dotenv import load_dotenv

from .exporter import TeamsExporter


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Export Microsoft Teams chat and channel logs from local cache."
    )
    parser.add_argument(
        "--teams-root",
        default=os.environ.get("TEAMS_ROOT"),
        help="Path to the Teams WV2Profile_tfw directory (or set TEAMS_ROOT env var)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=os.environ.get("OUTPUT", "output"),
        help="Output directory (default: OUTPUT env var or ./output)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    if not args.teams_root:
        parser.error(
            "Teams root directory not specified. "
            "Pass --teams-root or set TEAMS_ROOT in .env"
        )

    teams_root = pathlib.Path(args.teams_root)
    if not teams_root.exists():
        print(f"Error: Teams root directory not found: {teams_root}", file=sys.stderr)
        sys.exit(1)

    exporter = TeamsExporter(teams_root)
    exporter.export(args.output, verbose=not args.quiet)


if __name__ == "__main__":
    main()
