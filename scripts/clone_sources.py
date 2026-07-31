#!/usr/bin/env python3
"""
Clone quality sources from source_manifest.csv into raw/github/

Features:
- Auto-detects default branch (main, master, develop)
- Retries with fallback branches on failure
- Shallow clones by default for speed

Usage:
    python scripts/clone_sources.py [--min-quality 3] [--shallow]
    python scripts/clone_sources.py --manifest sources/merged_sources.csv
"""

import csv
import subprocess
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import argparse

# Try httpx for API calls, fall back to subprocess
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@dataclass
class Source:
    source_id: str
    kind: str
    repo_full_name: str
    ref: str
    quality: int
    notes: str


# Common branch names to try
BRANCH_FALLBACKS = ["main", "master", "develop", "dev"]


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
                notes=row.get("notes", ""),
            ))
    return sources


def get_default_branch(repo_full_name: str) -> Optional[str]:
    """Get the default branch using GitHub API."""
    if not HAS_HTTPX:
        return None

    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"https://api.github.com/repos/{repo_full_name}",
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json().get("default_branch")
    except Exception:
        pass
    return None


def try_clone(repo_url: str, target_dir: Path, branch: str, shallow: bool) -> bool:
    """Attempt to clone with a specific branch."""
    cmd = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    cmd.extend(["--branch", branch, repo_url, str(target_dir)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0


def clone_repo(source: Source, output_dir: Path, shallow: bool = True) -> bool:
    """Clone a single repository with auto branch detection."""
    repo_url = f"https://github.com/{source.repo_full_name}.git"
    target_dir = output_dir / source.source_id

    if target_dir.exists():
        print(f"  ⏭️  {source.source_id} already exists, skipping")
        return True

    print(f"  📦 Cloning {source.repo_full_name} -> {source.source_id}")

    # Build list of branches to try
    branches_to_try = []

    # First, try to get the actual default branch from API
    default_branch = get_default_branch(source.repo_full_name)
    if default_branch:
        branches_to_try.append(default_branch)

    # Add the specified ref if different
    if source.ref and source.ref not in branches_to_try:
        branches_to_try.append(source.ref)

    # Add fallbacks
    for branch in BRANCH_FALLBACKS:
        if branch not in branches_to_try:
            branches_to_try.append(branch)

    # Try each branch
    for branch in branches_to_try:
        try:
            if try_clone(repo_url, target_dir, branch, shallow):
                print(f"  ✅ Success (branch: {branch})")
                return True
        except subprocess.TimeoutExpired:
            print(f"  ❌ Timeout")
            return False
        except Exception:
            pass

        # Clean up failed attempt
        if target_dir.exists():
            import shutil
            shutil.rmtree(target_dir, ignore_errors=True)

    print(f"  ❌ Failed: No valid branch found (tried: {', '.join(branches_to_try[:3])})")
    return False


def main():
    parser = argparse.ArgumentParser(description="Clone Flutter repos from manifest")
    parser.add_argument("--min-quality", type=int, default=3, help="Minimum quality score (default: 3)")
    parser.add_argument("--shallow", action="store_true", default=True, help="Shallow clone (default: True)")
    parser.add_argument("--full", action="store_true", help="Full clone (overrides --shallow)")
    parser.add_argument("--manifest", type=str, help="Path to manifest CSV file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of repos to clone (0 = no limit)")
    args = parser.parse_args()

    shallow = not args.full

    # Paths
    project_root = Path(__file__).parent.parent
    manifest_path = Path(args.manifest) if args.manifest else project_root / "sources" / "source_manifest.csv"
    output_dir = project_root / "raw" / "github"

    # Ensure output dir exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load sources
    sources = load_sources(manifest_path, min_quality=args.min_quality)

    # Apply limit if specified
    if args.limit > 0:
        sources = sources[:args.limit]

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
