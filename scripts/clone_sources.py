#!/usr/bin/env python3
"""
Clone quality sources from source_manifest.csv into raw/github/

Usage:
    python scripts/clone_sources.py [--min-quality 4] [--shallow]
"""

import csv
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List
import argparse


@dataclass
class Source:
    source_id: str
    kind: str
    repo_full_name: str
    ref: str
    quality: int
    notes: str


def load_sources(manifest_path: Path, min_quality: int = 4) -> List[Source]:
    """Load sources from CSV, filtering by kind=repo and quality >= min_quality."""
    sources = []
    with open(manifest_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["kind"] != "repo":
                continue
            quality = int(row["quality"])
            if quality < min_quality:
                continue
            sources.append(Source(
                source_id=row["source_id"],
                kind=row["kind"],
                repo_full_name=row["repo_full_name"],
                ref=row["ref"],
                quality=quality,
                notes=row["notes"],
            ))
    return sources


def clone_repo(source: Source, output_dir: Path, shallow: bool = True) -> bool:
    """Clone a single repository. Returns True on success."""
    repo_url = f"https://github.com/{source.repo_full_name}.git"
    # Use source_id as folder name for consistency
    target_dir = output_dir / source.source_id

    if target_dir.exists():
        print(f"  ⏭️  {source.source_id} already exists, skipping")
        return True

    cmd = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    cmd.extend(["--branch", source.ref, repo_url, str(target_dir)])

    print(f"  📦 Cloning {source.repo_full_name} ({source.ref}) -> {source.source_id}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
        )
        if result.returncode != 0:
            print(f"  ❌ Failed: {result.stderr.strip()}")
            return False
        print(f"  ✅ Success")
        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ Timeout cloning {source.repo_full_name}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Clone Flutter repos from manifest")
    parser.add_argument("--min-quality", type=int, default=4, help="Minimum quality score (default: 4)")
    parser.add_argument("--shallow", action="store_true", default=True, help="Shallow clone (default: True)")
    parser.add_argument("--full", action="store_true", help="Full clone (overrides --shallow)")
    args = parser.parse_args()

    shallow = not args.full

    # Paths
    project_root = Path(__file__).parent.parent
    manifest_path = project_root / "sources" / "source_manifest.csv"
    output_dir = project_root / "raw" / "github"

    # Ensure output dir exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load sources
    sources = load_sources(manifest_path, min_quality=args.min_quality)
    print(f"\n🎯 Found {len(sources)} repos with quality >= {args.min_quality}\n")

    # Clone each
    success_count = 0
    fail_count = 0

    for source in sources:
        if clone_repo(source, output_dir, shallow=shallow):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"✅ Cloned: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"📁 Output: {output_dir}")
    print(f"{'='*50}\n")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
