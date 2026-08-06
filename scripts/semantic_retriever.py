#!/usr/bin/env python3
"""
Semantic retriever for Flutter code snippets.

Uses pre-computed embeddings and cosine similarity to find
semantically relevant code snippets for a given query.

Usage:
    from semantic_retriever import SemanticRetriever

    retriever = SemanticRetriever()
    results = retriever.search("login screen with email validation", top_k=10)
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


@dataclass
class SemanticMatch:
    """A semantically matched code snippet."""
    id: str
    name: str
    type: str
    patterns: List[str]
    repo_id: str
    score: float  # Cosine similarity score (0-1)
    code: Optional[str] = None  # Full code if loaded


@dataclass
class SnippetMetadata:
    """Snippet metadata from embeddings."""
    id: str
    name: str
    type: str
    patterns: List[str]
    repo_id: str


class SemanticRetriever:
    """
    Semantic code snippet retriever using pre-computed embeddings.

    Uses cosine similarity between query embedding and snippet embeddings
    to find the most relevant code examples.
    """

    def __init__(
        self,
        embeddings_dir: Optional[Path] = None,
        snippets_dir: Optional[Path] = None,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize the semantic retriever.

        Args:
            embeddings_dir: Path to embeddings directory
            snippets_dir: Path to snippets directory (for loading full code)
            model_name: Model name (must match embedding model)
        """
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers required. Install with: uv pip install sentence-transformers"
            )

        project_root = Path(__file__).parent.parent
        self.embeddings_dir = embeddings_dir or project_root / "curated" / "embeddings"
        self.snippets_dir = snippets_dir or project_root / "curated" / "snippets"
        self.model_name = model_name

        # Load embeddings and metadata
        self._load_embeddings()

        # Load the model for query encoding
        self.model = SentenceTransformer(model_name)

        # Lazy load full snippets
        self._full_snippets: Optional[Dict[str, dict]] = None

    def _load_embeddings(self):
        """Load pre-computed embeddings and metadata."""
        embeddings_file = self.embeddings_dir / "snippet_embeddings.npy"
        metadata_file = self.embeddings_dir / "embedding_metadata.json"

        if not embeddings_file.exists():
            raise FileNotFoundError(f"Embeddings not found: {embeddings_file}")

        # Load embeddings
        self.embeddings = np.load(embeddings_file)

        # Load metadata
        with open(metadata_file) as f:
            metadata = json.load(f)

        self.ids = metadata["ids"]
        self.snippets_meta = {
            s["id"]: SnippetMetadata(
                id=s["id"],
                name=s["name"],
                type=s["type"],
                patterns=s.get("patterns", []),
                repo_id=s.get("repo_id", ""),
            )
            for s in metadata["snippets"]
        }

        print(f"📚 Loaded {len(self.ids)} embeddings ({self.embeddings.shape[1]}-dim)")

    def _load_full_snippets(self):
        """Load full snippet code (lazy loaded on first access)."""
        if self._full_snippets is not None:
            return

        self._full_snippets = {}
        snippets_file = self.snippets_dir / "all_snippets.jsonl"

        if snippets_file.exists():
            with open(snippets_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        self._full_snippets[data["id"]] = data

    def _encode_query(self, query: str) -> np.ndarray:
        """Encode a query string to embedding."""
        embedding = self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding

    def search(
        self,
        query: str,
        top_k: int = 10,
        type_filter: Optional[str] = None,
        pattern_filter: Optional[List[str]] = None,
        include_code: bool = False,
    ) -> List[SemanticMatch]:
        """
        Search for semantically similar code snippets.

        Args:
            query: Natural language query or code description
            top_k: Number of results to return
            type_filter: Filter by type (widget, service, provider, model)
            pattern_filter: Filter by patterns (auth, forms, etc.)
            include_code: Whether to include full code in results

        Returns:
            List of SemanticMatch results sorted by similarity
        """
        # Encode query
        query_embedding = self._encode_query(query)

        # Compute cosine similarities (embeddings are normalized)
        similarities = np.dot(self.embeddings, query_embedding)

        # Get top-k indices
        # We get more than top_k to allow for filtering
        num_candidates = min(top_k * 5, len(self.ids))
        top_indices = np.argsort(similarities)[::-1][:num_candidates]

        # Build results with filtering
        results = []
        for idx in top_indices:
            if len(results) >= top_k:
                break

            snippet_id = self.ids[idx]
            meta = self.snippets_meta.get(snippet_id)
            if not meta:
                continue

            # Apply type filter
            if type_filter and meta.type != type_filter:
                continue

            # Apply pattern filter (any match)
            if pattern_filter:
                if not any(p in meta.patterns for p in pattern_filter):
                    continue

            # Get full code if requested
            code = None
            if include_code:
                self._load_full_snippets()
                if snippet_id in self._full_snippets:
                    code = self._full_snippets[snippet_id].get("code")

            results.append(SemanticMatch(
                id=snippet_id,
                name=meta.name,
                type=meta.type,
                patterns=meta.patterns,
                repo_id=meta.repo_id,
                score=float(similarities[idx]),
                code=code,
            ))

        return results

    def search_for_template(
        self,
        template: Dict,
        user_prompt: str = "",
        max_results: int = 10,
        include_code: bool = True,
    ) -> List[SemanticMatch]:
        """
        Search for snippets relevant to a template and user prompt.

        Combines template context with user prompt for better matching.

        Args:
            template: Template dictionary with name, screens, patterns, etc.
            user_prompt: User's natural language request
            max_results: Maximum number of results
            include_code: Whether to include full code

        Returns:
            List of SemanticMatch results
        """
        # Build query from template + user prompt
        query_parts = []

        # Add user prompt
        if user_prompt:
            query_parts.append(user_prompt)

        # Add template name and description
        if template.get("name"):
            query_parts.append(f"app type: {template['name']}")

        if template.get("description"):
            query_parts.append(template["description"])

        # Add screens
        if template.get("screens"):
            screens = template["screens"]
            if isinstance(screens, list):
                query_parts.append(f"screens: {', '.join(screens)}")

        # Add patterns
        if template.get("patterns"):
            patterns = template["patterns"]
            if isinstance(patterns, list):
                query_parts.append(f"patterns: {', '.join(patterns)}")

        # Combine into query
        query = "\n".join(query_parts)

        return self.search(
            query=query,
            top_k=max_results,
            include_code=include_code,
        )

    def search_similar_to_code(
        self,
        code: str,
        top_k: int = 5,
        include_code: bool = True,
    ) -> List[SemanticMatch]:
        """
        Find code snippets similar to a given code snippet.

        Useful for finding alternative implementations or related patterns.

        Args:
            code: Code snippet to find similar code for
            top_k: Number of results
            include_code: Whether to include full code

        Returns:
            List of similar code snippets
        """
        # Truncate code for embedding
        code_query = f"code:\n{code[:1500]}"
        return self.search(code_query, top_k=top_k, include_code=include_code)

    def to_context_string(
        self,
        matches: List[SemanticMatch],
        max_chars: int = 12000,
    ) -> str:
        """
        Convert matches to context string for LLM.

        Args:
            matches: List of semantic matches
            max_chars: Maximum characters in output

        Returns:
            Formatted context string with code snippets
        """
        if not matches:
            return ""

        lines = ["## REFERENCE CODE SNIPPETS (Semantic Match)\n"]
        lines.append("Use these production-quality examples as reference:\n")

        total_chars = sum(len(line) for line in lines)

        for i, match in enumerate(matches, 1):
            # Build snippet section
            section_lines = []
            section_lines.append(f"### {i}. {match.name} ({match.type}) [score: {match.score:.3f}]")

            if match.patterns:
                section_lines.append(f"Patterns: {', '.join(match.patterns)}")

            if match.code:
                # Truncate very long code
                code = match.code
                if len(code) > 2000:
                    code = code[:2000] + "\n// ... (truncated)"
                section_lines.append(f"\n```dart\n{code}\n```\n")

            section = "\n".join(section_lines)

            # Check if we have room
            if total_chars + len(section) > max_chars:
                break

            lines.append(section)
            total_chars += len(section)

        return "\n".join(lines)


def main():
    """Test semantic retriever."""
    retriever = SemanticRetriever()

    # Test queries
    test_queries = [
        "login screen with email and password authentication",
        "shopping cart with add remove items",
        "fetch data from REST API with loading state",
        "bottom navigation with multiple tabs",
        "form validation with error messages",
    ]

    print("\n" + "="*60)
    print("🔍 Semantic Retriever Test")
    print("="*60)

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        results = retriever.search(query, top_k=5, include_code=False)

        for i, match in enumerate(results, 1):
            print(f"   {i}. {match.name} ({match.type}) [score: {match.score:.3f}]")
            if match.patterns:
                print(f"      patterns: {match.patterns}")

    # Test with template
    print("\n" + "="*60)
    print("🎯 Template-based Search")
    print("="*60)

    template = {
        "name": "ECOMMERCE",
        "description": "Online shopping application",
        "screens": ["ProductList", "ProductDetail", "Cart", "Checkout"],
        "patterns": ["networking", "local_storage", "forms"],
    }

    results = retriever.search_for_template(
        template,
        user_prompt="build an online store with product catalog",
        max_results=8,
        include_code=True,
    )

    print(f"\nFound {len(results)} matches for ECOMMERCE template:\n")
    for match in results:
        print(f"  - {match.name} ({match.type}) [score: {match.score:.3f}] {match.patterns}")

    # Show context string preview
    print("\n" + "="*60)
    print("📄 Context String Preview")
    print("="*60)
    context = retriever.to_context_string(results[:3], max_chars=4000)
    print(context[:2000])
    if len(context) > 2000:
        print(f"\n... ({len(context) - 2000} more chars)")


if __name__ == "__main__":
    main()
