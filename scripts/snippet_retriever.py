#!/usr/bin/env python3
"""
Snippet Retriever - Retrieve relevant code snippets for generation.

Retrieves actual code implementations based on:
- Template requirements (screens, services, models)
- Pattern matching (auth, forms, navigation, etc.)
- Type matching (widget, service, provider, model)

Usage:
    from snippet_retriever import SnippetRetriever

    retriever = SnippetRetriever()
    snippets = retriever.retrieve_for_template(template, "food delivery app")
    context = retriever.to_context_string(snippets)
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional


@dataclass
class Snippet:
    id: str
    type: str
    name: str
    code: str
    patterns: List[str]
    lines: int
    repo_id: str


class SnippetRetriever:
    """Retrieve code snippets for generation context."""

    def __init__(self, snippets_dir: Optional[Path] = None):
        if snippets_dir is None:
            snippets_dir = Path(__file__).parent.parent / "curated" / "snippets"

        self.snippets_dir = Path(snippets_dir)
        self._snippets: Dict[str, Snippet] = {}
        self._by_type: Dict[str, List[str]] = {}
        self._by_pattern: Dict[str, List[str]] = {}
        self._by_name_keyword: Dict[str, List[str]] = {}

        self._load_snippets()

    def _load_snippets(self):
        """Load all snippets and build indexes."""
        snippets_file = self.snippets_dir / "all_snippets.jsonl"
        if not snippets_file.exists():
            print(f"⚠️  No snippets found at {snippets_file}")
            return

        with open(snippets_file, 'r') as f:
            for line in f:
                data = json.loads(line)
                snippet = Snippet(
                    id=data['id'],
                    type=data['type'],
                    name=data['name'],
                    code=data['code'],
                    patterns=data.get('patterns', []),
                    lines=data.get('lines', 0),
                    repo_id=data.get('repo_id', ''),
                )
                self._snippets[snippet.id] = snippet

                # Index by type
                if snippet.type not in self._by_type:
                    self._by_type[snippet.type] = []
                self._by_type[snippet.type].append(snippet.id)

                # Index by pattern
                for pattern in snippet.patterns:
                    if pattern not in self._by_pattern:
                        self._by_pattern[pattern] = []
                    self._by_pattern[pattern].append(snippet.id)

                # Index by name keywords
                keywords = self._extract_keywords(snippet.name)
                for kw in keywords:
                    if kw not in self._by_name_keyword:
                        self._by_name_keyword[kw] = []
                    self._by_name_keyword[kw].append(snippet.id)

        print(f"📚 Loaded {len(self._snippets)} snippets")
        print(f"   Types: {list(self._by_type.keys())}")
        print(f"   Patterns: {list(self._by_pattern.keys())}")

    def _extract_keywords(self, name: str) -> List[str]:
        """Extract keywords from class name."""
        # Split CamelCase
        words = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
        return [w.lower() for w in words if len(w) > 2]

    def retrieve_by_pattern(
        self,
        patterns: List[str],
        limit: int = 5,
    ) -> List[Snippet]:
        """Retrieve snippets matching patterns."""
        results = []
        seen = set()

        for pattern in patterns:
            if pattern in self._by_pattern:
                for snippet_id in self._by_pattern[pattern]:
                    if snippet_id not in seen and len(results) < limit * len(patterns):
                        seen.add(snippet_id)
                        results.append(self._snippets[snippet_id])

        # Sort by relevance (more patterns matched = better)
        def score(s):
            return sum(1 for p in patterns if p in s.patterns)
        results.sort(key=score, reverse=True)

        return results[:limit]

    def retrieve_by_type(
        self,
        snippet_type: str,
        keywords: List[str] = None,
        limit: int = 5,
    ) -> List[Snippet]:
        """Retrieve snippets by type, optionally filtered by keywords."""
        if snippet_type not in self._by_type:
            return []

        candidates = [self._snippets[sid] for sid in self._by_type[snippet_type]]

        if keywords:
            # Score by keyword match
            def keyword_score(s):
                name_lower = s.name.lower()
                return sum(1 for kw in keywords if kw in name_lower)

            candidates = [s for s in candidates if keyword_score(s) > 0]
            candidates.sort(key=keyword_score, reverse=True)

        return candidates[:limit]

    def retrieve_by_keywords(
        self,
        keywords: List[str],
        limit: int = 10,
    ) -> List[Snippet]:
        """Retrieve snippets matching keywords in name."""
        results = []
        seen = set()
        scores = {}

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in self._by_name_keyword:
                for snippet_id in self._by_name_keyword[kw_lower]:
                    if snippet_id not in seen:
                        seen.add(snippet_id)
                        scores[snippet_id] = scores.get(snippet_id, 0) + 1

        # Sort by score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        for sid in sorted_ids[:limit]:
            results.append(self._snippets[sid])

        return results

    def retrieve_for_template(
        self,
        template: Dict,
        user_prompt: str = "",
        max_snippets: int = 10,
        max_chars: int = 8000,
    ) -> List[Snippet]:
        """
        Retrieve relevant snippets for a template.

        Strategy:
        1. Get snippets matching template screens/features
        2. Get snippets matching detected patterns
        3. Get snippets matching user prompt keywords
        4. Dedupe and limit by character budget
        """
        results = []
        seen = set()

        # Extract keywords from template
        template_keywords = []
        for screen in template.get('screens', []):
            template_keywords.extend(self._extract_keywords(screen))
        for feature in template.get('key_features', []):
            template_keywords.extend(self._extract_keywords(feature))

        # Extract keywords from user prompt
        prompt_keywords = [w.lower() for w in re.findall(r'\w+', user_prompt) if len(w) > 3]

        # Combine keywords
        all_keywords = list(set(template_keywords + prompt_keywords))

        # 1. Get widgets matching keywords
        widgets = self.retrieve_by_type('widget', all_keywords, limit=5)
        for s in widgets:
            if s.id not in seen:
                seen.add(s.id)
                results.append(s)

        # 2. Get services matching keywords
        services = self.retrieve_by_type('service', all_keywords, limit=3)
        for s in services:
            if s.id not in seen:
                seen.add(s.id)
                results.append(s)

        # 3. Get providers if Riverpod is used
        if template.get('state_management') == 'riverpod':
            providers = self.retrieve_by_pattern(['riverpod'], limit=2)
            for s in providers:
                if s.id not in seen:
                    seen.add(s.id)
                    results.append(s)

        # 4. Get pattern-specific snippets
        feature_patterns = []
        if 'auth' in all_keywords or 'login' in all_keywords:
            feature_patterns.append('auth')
        if 'form' in all_keywords:
            feature_patterns.append('forms')
        if 'map' in all_keywords or 'location' in all_keywords:
            feature_patterns.append('navigation')

        if feature_patterns:
            pattern_snippets = self.retrieve_by_pattern(feature_patterns, limit=3)
            for s in pattern_snippets:
                if s.id not in seen:
                    seen.add(s.id)
                    results.append(s)

        # Limit by character budget
        limited = []
        total_chars = 0
        for s in results:
            if total_chars + len(s.code) > max_chars:
                break
            limited.append(s)
            total_chars += len(s.code)

        return limited[:max_snippets]

    def to_context_string(
        self,
        snippets: List[Snippet],
        include_full_code: bool = True,
    ) -> str:
        """Convert snippets to context string for LLM."""
        if not snippets:
            return ""

        parts = ["## REFERENCE CODE SNIPPETS\n"]
        parts.append("Use these as reference for generating similar code:\n")

        for i, s in enumerate(snippets, 1):
            parts.append(f"\n### {i}. {s.name} ({s.type})")
            if s.patterns:
                parts.append(f"Patterns: {', '.join(s.patterns)}")

            if include_full_code:
                parts.append(f"\n```dart\n{s.code}\n```")
            else:
                # Just show first few lines as hint
                lines = s.code.split('\n')[:10]
                parts.append(f"\n```dart\n{''.join(lines)}\n// ... ({s.lines} lines total)\n```")

        return '\n'.join(parts)


def main():
    """Test the retriever."""
    import yaml

    retriever = SnippetRetriever()

    # Load a template
    templates_file = Path(__file__).parent.parent / "templates" / "template_registry.yaml"
    with open(templates_file) as f:
        data = yaml.safe_load(f)
        templates = data.get('templates', data)

    # Find food delivery template
    template = next((t for t in templates if t['name'] == 'FOOD_DELIVERY'), templates[0])

    print(f"\n🔍 Retrieving snippets for: {template['name']}\n")

    snippets = retriever.retrieve_for_template(
        template,
        user_prompt="Build a food delivery app with restaurant listings and cart"
    )

    print(f"Found {len(snippets)} relevant snippets:\n")
    for s in snippets:
        print(f"  - {s.name} ({s.type}) [{s.lines} lines] patterns={s.patterns}")

    print("\n" + "="*60)
    print("CONTEXT STRING PREVIEW:")
    print("="*60)
    context = retriever.to_context_string(snippets[:3])
    print(context[:2000] + "..." if len(context) > 2000 else context)


if __name__ == "__main__":
    main()
