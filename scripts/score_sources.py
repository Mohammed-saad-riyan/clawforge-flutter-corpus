"""Score candidate sources for promotion into curated corpus slices."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"


def main() -> None:
    manifest = SOURCES / "source_manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"scoring {len(rows)} sources")
    for row in rows:
        print(f"{row['source_id']}: {row['repo_full_name']} -> {row['quality']}")


if __name__ == "__main__":
    main()
