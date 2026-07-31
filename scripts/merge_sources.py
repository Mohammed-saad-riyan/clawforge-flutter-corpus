#!/usr/bin/env python3
"""
Merge discovered repos with existing source manifest.

Deduplicates, applies quality filters, and creates a unified source list.

Usage:
    python scripts/merge_sources.py --min-quality 3
"""

import csv
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Set


@dataclass
class Source:
    source_id: str
    kind: str
    repo_full_name: str
    ref: str
    quality: int
    notes: str = ""


def load_existing_sources(path: Path) -> List[Source]:
    """Load existing source manifest."""
    sources = []
    if not path.exists():
        return sources

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["kind"] != "repo":
                continue
            sources.append(Source(
                source_id=row["source_id"],
                kind=row["kind"],
                repo_full_name=row["repo_full_name"],
                ref=row["ref"],
                quality=int(row["quality"]),
                notes=row.get("notes", ""),
            ))
    return sources


def load_discovered_repos(path: Path, min_quality: int = 3) -> List[Source]:
    """Load discovered repos from CSV."""
    sources = []
    if not path.exists():
        return sources

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            quality = int(row["quality"])
            if quality < min_quality:
                continue

            stars = row.get("stars", "0")
            description = row.get("description", "")[:50]
            notes = f"★{stars} {description}"

            sources.append(Source(
                source_id=row["source_id"],
                kind="repo",
                repo_full_name=row["repo_full_name"],
                ref=row["ref"],
                quality=quality,
                notes=notes,
            ))
    return sources


def merge_sources(
    existing: List[Source],
    discovered: List[Source],
) -> List[Source]:
    """Merge sources, deduplicating by repo name."""
    seen_repos: Set[str] = set()
    merged = []

    # Existing sources have priority
    for s in existing:
        repo_name = s.repo_full_name.lower()
        if repo_name not in seen_repos:
            seen_repos.add(repo_name)
            merged.append(s)

    # Add discovered sources
    next_id = 100  # Start discovered IDs at S100
    for s in discovered:
        repo_name = s.repo_full_name.lower()
        if repo_name not in seen_repos:
            seen_repos.add(repo_name)
            # Renumber to avoid conflicts
            s.source_id = f"S{next_id:03d}"
            next_id += 1
            merged.append(s)

    return merged


def save_merged(sources: List[Source], path: Path):
    """Save merged sources to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_id", "kind", "repo_full_name", "ref", "quality", "notes"])

        for s in sources:
            writer.writerow([
                s.source_id,
                s.kind,
                s.repo_full_name,
                s.ref,
                s.quality,
                s.notes,
            ])

    print(f"💾 Saved {len(sources)} sources to {path}")


def main():
    parser = argparse.ArgumentParser(description="Merge source manifests")
    parser.add_argument("--min-quality", type=int, default=3, help="Minimum quality to include")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    existing_path = project_root / "sources" / "source_manifest.csv"
    discovered_path = project_root / "sources" / "discovered_repos.csv"
    output_path = project_root / "sources" / "merged_sources.csv"

    print(f"\n📂 Loading sources...\n")

    existing = load_existing_sources(existing_path)
    print(f"  Existing: {len(existing)} repos")

    discovered = load_discovered_repos(discovered_path, min_quality=args.min_quality)
    print(f"  Discovered (quality >= {args.min_quality}): {len(discovered)} repos")

    merged = merge_sources(existing, discovered)
    print(f"  Merged (deduplicated): {len(merged)} repos")

    # Quality breakdown
    quality_dist = {}
    for s in merged:
        quality_dist[s.quality] = quality_dist.get(s.quality, 0) + 1

    print(f"\n  Quality distribution:")
    for q in sorted(quality_dist.keys(), reverse=True):
        print(f"    Quality {q}: {quality_dist[q]} repos")

    save_merged(merged, output_path)

    print(f"\n✅ Ready to clone with:")
    print(f"   python scripts/clone_sources.py --manifest sources/merged_sources.csv\n")


if __name__ == "__main__":
    main()
