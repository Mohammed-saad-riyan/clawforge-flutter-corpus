"""Build or refresh source manifests for the Flutter corpus.

This script is intentionally minimal so it can be extended later with GitHub API
pulls, repo scoring, and incremental sync logic.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"


def main() -> None:
    csv_path = SOURCES / "source_manifest.csv"
    jsonl_path = SOURCES / "source_manifest.jsonl"
    print(f"manifest csv: {csv_path}")
    print(f"manifest jsonl: {jsonl_path}")

    if not csv_path.exists() or not jsonl_path.exists():
        raise SystemExit("manifest files are missing")

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"loaded {len(rows)} sources")


if __name__ == "__main__":
    main()
