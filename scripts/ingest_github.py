"""Ingest GitHub repositories into the Flutter corpus.

This is a scaffold for later expansion into full cloning, diff capture,
AST extraction, and curated promotion.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
RAW = ROOT / "raw" / "github"


@dataclass(frozen=True)
class Source:
    source_id: str
    kind: str
    repo_full_name: str
    ref: str
    quality: int
    notes: str


def load_sources() -> list[Source]:
    manifest = SOURCES / "source_manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            Source(
                source_id=row["source_id"],
                kind=row["kind"],
                repo_full_name=row["repo_full_name"],
                ref=row["ref"],
                quality=int(row["quality"]),
                notes=row.get("notes", ""),
            )
            for row in reader
        ]


def main() -> None:
    sources = load_sources()
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"loaded {len(sources)} sources")
    print(f"raw output root: {RAW}")
    for source in sources:
        print(f"- {source.source_id} {source.repo_full_name}@{source.ref} q={source.quality}")


if __name__ == "__main__":
    main()
