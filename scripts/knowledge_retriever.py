#!/usr/bin/env python3
"""
Knowledge Retriever - Search extracted Flutter knowledge.

Retrieves relevant widgets, patterns, and code examples based on:
1. Template requirements
2. User prompt keywords
3. Pattern matching

Usage:
    from knowledge_retriever import KnowledgeRetriever

    retriever = KnowledgeRetriever()
    context = retriever.retrieve_for_template("FOOD_DELIVERY", user_prompt="...")
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict


@dataclass
class RetrievedWidget:
    name: str
    widget_type: str
    file_path: str
    repo_id: str
    extends: Optional[str] = None
    patterns: List[str] = field(default_factory=list)


@dataclass
class RetrievedPattern:
    name: str
    examples: List[str]  # File paths
    packages: List[str]


@dataclass
class RetrievalResult:
    widgets: List[RetrievedWidget]
    patterns: List[RetrievedPattern]
    packages: List[str]
    example_files: List[str]

    def to_context_string(self, max_widgets: int = 10, max_patterns: int = 5) -> str:
        """Convert to a context string for the LLM."""
        parts = []

        if self.patterns:
            parts.append("PATTERNS TO USE:")
            for p in self.patterns[:max_patterns]:
                parts.append(f"  - {p.name}: packages={', '.join(p.packages[:5])}")
            parts.append("")

        if self.widgets:
            parts.append("WIDGET EXAMPLES:")
            for w in self.widgets[:max_widgets]:
                parts.append(f"  - {w.name} ({w.widget_type}) from {w.repo_id}")
                if w.extends:
                    parts.append(f"    extends: {w.extends}")
            parts.append("")

        if self.packages:
            parts.append("RECOMMENDED PACKAGES:")
            parts.append(f"  {', '.join(self.packages[:20])}")
            parts.append("")

        return "\n".join(parts)


class KnowledgeRetriever:
    """Search and retrieve Flutter knowledge from extracted data."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        """
        Initialize retriever.

        Args:
            knowledge_dir: Path to curated/extracted directory
        """
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent.parent / "curated" / "extracted"

        self.knowledge_dir = Path(knowledge_dir)
        self._index: Dict = {}
        self._widget_index: Dict[str, List[RetrievedWidget]] = defaultdict(list)
        self._pattern_index: Dict[str, List[str]] = defaultdict(list)
        self._package_index: Dict[str, Set[str]] = defaultdict(set)

        self._load_index()

    def _load_index(self):
        """Load and index all extracted knowledge."""
        summary_file = self.knowledge_dir / "extraction_summary.json"
        if not summary_file.exists():
            print(f"⚠️  No extraction summary found at {summary_file}")
            return

        with open(summary_file) as f:
            self._index = json.load(f)

        # Build indexes from individual repo knowledge files
        for repo_info in self._index.get("repos", []):
            repo_id = repo_info["repo_id"]
            knowledge_file = self.knowledge_dir / f"{repo_id}_knowledge.json"

            if not knowledge_file.exists():
                continue

            with open(knowledge_file) as f:
                repo_data = json.load(f)

            # Index widgets by type
            for file_data in repo_data.get("files", []):
                if isinstance(file_data, dict):
                    for cls in file_data.get("classes", []):
                        if cls.get("is_widget"):
                            widget = RetrievedWidget(
                                name=cls["name"],
                                widget_type=cls.get("widget_type", "unknown"),
                                file_path=cls.get("file_path", ""),
                                repo_id=repo_id,
                                extends=cls.get("extends"),
                                patterns=file_data.get("patterns_detected", []),
                            )
                            # Index by widget type
                            self._widget_index[widget.widget_type].append(widget)
                            # Index by name keywords
                            for keyword in self._extract_keywords(widget.name):
                                self._widget_index[keyword].append(widget)

            # Index patterns and packages
            summary = repo_info.get("summary", {})
            for pattern in summary.get("patterns_detected", []):
                self._pattern_index[pattern].append(repo_id)

            for package in summary.get("packages_used", []):
                self._package_index[package].add(repo_id)

        print(f"📚 Loaded {len(self._widget_index)} widget indexes")
        print(f"📚 Loaded {len(self._pattern_index)} pattern indexes")
        print(f"📚 Loaded {len(self._package_index)} package indexes")

    def _extract_keywords(self, name: str) -> List[str]:
        """Extract searchable keywords from a class/widget name."""
        # Split CamelCase
        words = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
        return [w.lower() for w in words if len(w) > 2]

    def retrieve_for_template(
        self,
        template: Dict,
        user_prompt: str = "",
        max_widgets: int = 20,
        max_patterns: int = 10,
    ) -> RetrievalResult:
        """
        Retrieve knowledge relevant to a template.

        Args:
            template: Template dict from template_registry.yaml
            user_prompt: User's original prompt for keyword extraction
            max_widgets: Maximum widgets to return
            max_patterns: Maximum patterns to return

        Returns:
            RetrievalResult with relevant knowledge
        """
        # Extract search terms
        search_terms = set()

        # From template keywords
        for kw in template.get("keywords", []):
            search_terms.add(kw.lower())

        # From template screens
        for screen in template.get("screens", []):
            search_terms.update(self._extract_keywords(screen))

        # From user prompt
        prompt_words = re.findall(r'\w+', user_prompt.lower())
        for word in prompt_words:
            if len(word) > 3:
                search_terms.add(word)

        # Retrieve widgets
        widgets = []
        seen_widgets = set()
        for term in search_terms:
            for widget in self._widget_index.get(term, []):
                if widget.name not in seen_widgets:
                    widgets.append(widget)
                    seen_widgets.add(widget.name)
                    if len(widgets) >= max_widgets:
                        break

        # Retrieve patterns
        patterns = []
        template_patterns = template.get("patterns", [])
        for pattern_name in template_patterns:
            if pattern_name in self._pattern_index:
                patterns.append(RetrievedPattern(
                    name=pattern_name,
                    examples=self._pattern_index[pattern_name],
                    packages=self._get_packages_for_pattern(pattern_name),
                ))

        # Also get patterns from search terms
        for term in search_terms:
            if term in self._pattern_index and len(patterns) < max_patterns:
                if not any(p.name == term for p in patterns):
                    patterns.append(RetrievedPattern(
                        name=term,
                        examples=self._pattern_index[term],
                        packages=self._get_packages_for_pattern(term),
                    ))

        # Get recommended packages
        packages = set(template.get("packages", []))
        for pattern in patterns:
            packages.update(pattern.packages)

        # Get example files
        example_files = []
        for widget in widgets[:5]:
            if widget.file_path:
                example_files.append(widget.file_path)

        return RetrievalResult(
            widgets=widgets,
            patterns=patterns,
            packages=sorted(packages),
            example_files=example_files,
        )

    def _get_packages_for_pattern(self, pattern: str) -> List[str]:
        """Get commonly used packages for a pattern."""
        pattern_packages = {
            "riverpod": ["flutter_riverpod", "riverpod_annotation", "riverpod_generator"],
            "bloc": ["flutter_bloc", "bloc", "equatable"],
            "go_router": ["go_router"],
            "dio": ["dio", "retrofit", "pretty_dio_logger"],
            "freezed": ["freezed", "freezed_annotation", "json_serializable"],
            "hive": ["hive", "hive_flutter"],
            "repository": ["dartz", "either_dart"],
            "service": ["get_it", "injectable"],
        }
        return pattern_packages.get(pattern, [])

    def search_widgets(
        self,
        query: str,
        widget_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[RetrievedWidget]:
        """
        Search for widgets by name or type.

        Args:
            query: Search query
            widget_type: Filter by widget type (stateless, stateful, consumer, etc.)
            limit: Maximum results

        Returns:
            List of matching widgets
        """
        results = []
        query_lower = query.lower()

        # Search by query keywords
        keywords = self._extract_keywords(query) + [query_lower]

        for keyword in keywords:
            for widget in self._widget_index.get(keyword, []):
                if widget_type and widget.widget_type != widget_type:
                    continue
                if widget not in results:
                    results.append(widget)
                    if len(results) >= limit:
                        return results

        return results

    def get_packages_for_feature(self, feature: str) -> List[str]:
        """Get recommended packages for a feature."""
        feature_packages = {
            "auth": ["firebase_auth", "google_sign_in", "flutter_secure_storage"],
            "maps": ["google_maps_flutter", "geolocator", "geocoding"],
            "payments": ["flutter_stripe", "in_app_purchase"],
            "camera": ["camera", "image_picker", "image_cropper"],
            "video": ["video_player", "chewie"],
            "audio": ["just_audio", "audioplayers"],
            "notifications": ["firebase_messaging", "flutter_local_notifications"],
            "storage": ["shared_preferences", "hive", "sqflite"],
            "network": ["dio", "http", "connectivity_plus"],
            "ui": ["flutter_svg", "cached_network_image", "shimmer", "lottie"],
            "state": ["flutter_riverpod", "riverpod_annotation"],
            "routing": ["go_router"],
            "forms": ["reactive_forms", "flutter_form_builder"],
            "animations": ["flutter_animate", "rive"],
        }
        return feature_packages.get(feature.lower(), [])


if __name__ == "__main__":
    import sys
    import yaml

    # Load a template and test retrieval
    retriever = KnowledgeRetriever()

    # Load template registry
    template_file = Path(__file__).parent.parent / "templates" / "template_registry.yaml"
    with open(template_file) as f:
        templates = yaml.safe_load(f)

    # Get first template as example
    template = templates[0]  # SOCIAL_MEDIA
    print(f"\n🔍 Testing retrieval for template: {template['name']}\n")

    result = retriever.retrieve_for_template(
        template,
        user_prompt="I want to build a social media app with posts and comments"
    )

    print("📊 RETRIEVAL RESULTS:")
    print(f"  Widgets found: {len(result.widgets)}")
    print(f"  Patterns found: {len(result.patterns)}")
    print(f"  Packages recommended: {len(result.packages)}")

    print("\n📝 CONTEXT STRING:")
    print(result.to_context_string())
