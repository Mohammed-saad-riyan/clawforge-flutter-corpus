#!/usr/bin/env python3
"""
GitHub Flutter Repository Discovery

Discovers quality Flutter repositories using GitHub Search API.
Scores them based on stars, recent activity, and Flutter patterns.

Usage:
    python scripts/discover_repos.py --limit 500
    python scripts/discover_repos.py --limit 100 --min-stars 50

Requires: GITHUB_TOKEN environment variable for higher rate limits.
"""

import os
import csv
import json
import time
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import httpx


@dataclass
class RepoCandidate:
    repo_full_name: str
    stars: int
    forks: int
    last_push: str
    description: str
    topics: List[str]
    has_pubspec: bool
    estimated_quality: int  # 1-5
    discovery_query: str


class GitHubDiscovery:
    """Discover Flutter repos from GitHub."""

    BASE_URL = "https://api.github.com"

    # Search queries for different Flutter patterns
    SEARCH_QUERIES = [
        # High-quality architecture patterns
        "flutter riverpod clean architecture language:dart stars:>50",
        "flutter bloc clean architecture language:dart stars:>50",
        "flutter mvvm riverpod language:dart stars:>30",
        "flutter go_router riverpod language:dart stars:>20",

        # Production templates
        "flutter template production language:dart stars:>100",
        "flutter boilerplate riverpod language:dart stars:>50",
        "flutter starter clean language:dart stars:>30",

        # App categories
        "flutter ecommerce app language:dart stars:>50",
        "flutter food delivery language:dart stars:>20",
        "flutter chat app language:dart stars:>30",
        "flutter social media language:dart stars:>30",
        "flutter fitness app language:dart stars:>20",
        "flutter finance app language:dart stars:>30",
        "flutter booking app language:dart stars:>20",

        # State management examples
        "flutter riverpod example language:dart stars:>30",
        "flutter bloc example language:dart stars:>50",
        "flutter provider example language:dart stars:>30",

        # UI patterns
        "flutter ui kit language:dart stars:>100",
        "flutter animations language:dart stars:>50",
        "flutter responsive language:dart stars:>30",

        # Testing and quality
        "flutter testing example language:dart stars:>30",
        "flutter tdd language:dart stars:>20",

        # Specific features
        "flutter firebase auth language:dart stars:>30",
        "flutter google maps language:dart stars:>30",
        "flutter push notifications language:dart stars:>20",
        "flutter offline first language:dart stars:>20",

        # General popular
        "flutter app language:dart stars:>500",
        "flutter language:dart stars:>1000 pushed:>2024-01-01",
    ]

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.Client(timeout=30.0, headers=self.headers)
        self._seen_repos = set()
        self._rate_limit_remaining = 30

    def _check_rate_limit(self):
        """Check and handle rate limiting."""
        if self._rate_limit_remaining < 5:
            print("  ⏳ Rate limit low, waiting 60s...")
            time.sleep(60)
            self._rate_limit_remaining = 30

    def search_repos(self, query: str, max_results: int = 100) -> List[Dict]:
        """Search GitHub for repos matching query."""
        repos = []
        per_page = min(100, max_results)
        pages = (max_results + per_page - 1) // per_page

        for page in range(1, pages + 1):
            self._check_rate_limit()

            try:
                response = self._client.get(
                    f"{self.BASE_URL}/search/repositories",
                    params={
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": per_page,
                        "page": page,
                    },
                )

                # Update rate limit tracking
                self._rate_limit_remaining = int(
                    response.headers.get("x-ratelimit-remaining", 30)
                )

                if response.status_code == 403:
                    print("  ⚠️  Rate limited, waiting...")
                    time.sleep(60)
                    continue

                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                repos.extend(items)

                if len(items) < per_page:
                    break  # No more results

                time.sleep(1)  # Be nice to API

            except Exception as e:
                print(f"  ❌ Error searching: {e}")
                break

        return repos

    def check_has_pubspec(self, repo_full_name: str) -> bool:
        """Check if repo has pubspec.yaml (is a Flutter/Dart project)."""
        self._check_rate_limit()

        try:
            response = self._client.get(
                f"{self.BASE_URL}/repos/{repo_full_name}/contents/pubspec.yaml"
            )
            self._rate_limit_remaining = int(
                response.headers.get("x-ratelimit-remaining", 30)
            )
            return response.status_code == 200
        except Exception:
            return False

    def estimate_quality(self, repo: Dict) -> int:
        """Estimate repo quality (1-5) based on signals."""
        score = 0
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        topics = repo.get("topics", [])
        description = repo.get("description", "") or ""
        pushed_at = repo.get("pushed_at", "")

        # Stars scoring
        if stars >= 1000:
            score += 2
        elif stars >= 500:
            score += 1.5
        elif stars >= 100:
            score += 1
        elif stars >= 50:
            score += 0.5

        # Recent activity
        if pushed_at:
            try:
                push_date = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                days_ago = (datetime.now(push_date.tzinfo) - push_date).days
                if days_ago < 90:
                    score += 1
                elif days_ago < 180:
                    score += 0.5
            except Exception:
                pass

        # Quality indicators in topics/description
        quality_keywords = [
            "clean-architecture", "riverpod", "bloc", "production",
            "mvvm", "tdd", "testing", "enterprise"
        ]
        desc_lower = description.lower()
        for kw in quality_keywords:
            if kw in topics or kw.replace("-", " ") in desc_lower:
                score += 0.3

        # Community engagement
        if forks >= 100:
            score += 0.5
        elif forks >= 50:
            score += 0.3

        # Normalize to 1-5
        if score >= 4:
            return 5
        elif score >= 3:
            return 4
        elif score >= 2:
            return 3
        elif score >= 1:
            return 2
        else:
            return 1

    def discover(
        self,
        limit: int = 500,
        min_stars: int = 20,
        verify_pubspec: bool = False,
    ) -> List[RepoCandidate]:
        """
        Discover Flutter repos.

        Args:
            limit: Maximum repos to return
            min_stars: Minimum stars filter
            verify_pubspec: Check for pubspec.yaml (slower, uses more API calls)

        Returns:
            List of RepoCandidate objects
        """
        candidates = []

        print(f"\n🔍 Discovering Flutter repos (limit={limit}, min_stars={min_stars})\n")

        for query in self.SEARCH_QUERIES:
            if len(candidates) >= limit:
                break

            print(f"  📡 Query: {query[:60]}...")

            repos = self.search_repos(query, max_results=100)

            for repo in repos:
                if len(candidates) >= limit:
                    break

                full_name = repo.get("full_name")
                stars = repo.get("stargazers_count", 0)

                # Skip if already seen or below threshold
                if full_name in self._seen_repos:
                    continue
                if stars < min_stars:
                    continue

                self._seen_repos.add(full_name)

                # Verify pubspec if requested
                has_pubspec = True
                if verify_pubspec:
                    has_pubspec = self.check_has_pubspec(full_name)
                    if not has_pubspec:
                        continue

                candidate = RepoCandidate(
                    repo_full_name=full_name,
                    stars=stars,
                    forks=repo.get("forks_count", 0),
                    last_push=repo.get("pushed_at", ""),
                    description=(repo.get("description") or "")[:200],
                    topics=repo.get("topics", [])[:10],
                    has_pubspec=has_pubspec,
                    estimated_quality=self.estimate_quality(repo),
                    discovery_query=query[:50],
                )
                candidates.append(candidate)

            print(f"     Found {len(candidates)} candidates so far")

        # Sort by quality and stars
        candidates.sort(key=lambda x: (x.estimated_quality, x.stars), reverse=True)

        return candidates[:limit]

    def close(self):
        self._client.close()


def save_candidates(candidates: List[RepoCandidate], output_path: Path):
    """Save candidates to CSV file."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "source_id", "kind", "repo_full_name", "ref", "quality",
            "stars", "forks", "last_push", "description", "topics"
        ])

        for i, c in enumerate(candidates):
            source_id = f"D{i+1:04d}"  # D0001, D0002, etc.
            writer.writerow([
                source_id,
                "repo",
                c.repo_full_name,
                "main",  # Default branch
                c.estimated_quality,
                c.stars,
                c.forks,
                c.last_push[:10] if c.last_push else "",
                c.description[:100],
                ";".join(c.topics[:5]),
            ])

    print(f"\n💾 Saved {len(candidates)} candidates to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Discover Flutter repos from GitHub")
    parser.add_argument("--limit", type=int, default=500, help="Max repos to discover")
    parser.add_argument("--min-stars", type=int, default=20, help="Minimum stars")
    parser.add_argument("--verify-pubspec", action="store_true", help="Verify pubspec.yaml exists")
    parser.add_argument("--output", type=str, help="Output CSV file")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    output_path = Path(args.output) if args.output else project_root / "sources" / "discovered_repos.csv"

    discovery = GitHubDiscovery()

    try:
        candidates = discovery.discover(
            limit=args.limit,
            min_stars=args.min_stars,
            verify_pubspec=args.verify_pubspec,
        )

        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 DISCOVERY SUMMARY")
        print(f"{'='*60}")
        print(f"  Total discovered: {len(candidates)}")

        quality_dist = {}
        for c in candidates:
            quality_dist[c.estimated_quality] = quality_dist.get(c.estimated_quality, 0) + 1

        print(f"\n  Quality distribution:")
        for q in sorted(quality_dist.keys(), reverse=True):
            print(f"    Quality {q}: {quality_dist[q]} repos")

        print(f"\n  Top 10 by stars:")
        for c in candidates[:10]:
            print(f"    ⭐ {c.stars:>5} | Q{c.estimated_quality} | {c.repo_full_name}")

        print(f"{'='*60}\n")

        # Save results
        save_candidates(candidates, output_path)

    finally:
        discovery.close()


if __name__ == "__main__":
    main()
