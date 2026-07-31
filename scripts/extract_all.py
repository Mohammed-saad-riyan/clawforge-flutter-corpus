#!/usr/bin/env python3
"""
Run AST extraction on all cloned repositories.

Usage:
    python scripts/extract_all.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Import the extractor
from dart_ast_extractor import process_directory, serialize_results


def main():
    project_root = Path(__file__).parent.parent
    raw_github = project_root / "raw" / "github"
    output_dir = project_root / "curated" / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not raw_github.exists():
        print("❌ No repos found in raw/github/")
        sys.exit(1)

    repos = sorted([d for d in raw_github.iterdir() if d.is_dir() and not d.name.startswith(".")])
    print(f"\n🚀 Extracting knowledge from {len(repos)} repositories\n")

    all_results = []
    totals = {
        "files": 0,
        "classes": 0,
        "widgets": 0,
        "providers": 0,
        "packages": set(),
        "patterns": set(),
    }

    for repo_dir in repos:
        print(f"\n📂 {repo_dir.name}")
        print("-" * 40)

        results = process_directory(repo_dir)
        summary = results["summary"]

        # Update totals
        totals["files"] += summary["total_files"]
        totals["classes"] += summary["total_classes"]
        totals["widgets"] += summary["total_widgets"]
        totals["providers"] += summary["total_providers"]
        totals["packages"].update(summary["packages_used"])
        totals["patterns"].update(summary["patterns_detected"])

        # Save individual results
        output = serialize_results(results)
        output_file = output_dir / f"{repo_dir.name}_knowledge.json"
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        all_results.append({
            "repo_id": repo_dir.name,
            "project_name": results["project"].name if results["project"] else "unknown",
            "summary": summary,
        })

    # Create combined summary
    combined = {
        "extracted_at": datetime.now().isoformat(),
        "total_repos": len(repos),
        "totals": {
            "files": totals["files"],
            "classes": totals["classes"],
            "widgets": totals["widgets"],
            "providers": totals["providers"],
            "unique_packages": sorted(totals["packages"]),
            "unique_patterns": sorted(totals["patterns"]),
        },
        "repos": all_results,
    }

    # Save combined summary
    summary_file = output_dir / "extraction_summary.json"
    with open(summary_file, "w") as f:
        json.dump(combined, f, indent=2)

    # Print final summary
    print(f"\n{'='*60}")
    print(f"🎉 EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Repositories:      {len(repos)}")
    print(f"  Total Files:       {totals['files']}")
    print(f"  Total Classes:     {totals['classes']}")
    print(f"  Total Widgets:     {totals['widgets']}")
    print(f"  Total Providers:   {totals['providers']}")
    print(f"  Unique Packages:   {len(totals['packages'])}")
    print(f"  Unique Patterns:   {len(totals['patterns'])}")
    print(f"\n  Patterns Found:    {', '.join(sorted(totals['patterns']))}")
    print(f"\n  Output Directory:  {output_dir}")
    print(f"  Summary File:      {summary_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
