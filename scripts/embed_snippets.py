#!/usr/bin/env python3
"""
Generate semantic embeddings for code snippets.

Uses sentence-transformers to create dense vector representations
of code snippets for semantic similarity search.

Usage:
    python scripts/embed_snippets.py
    python scripts/embed_snippets.py --model all-MiniLM-L6-v2
"""

import json
import argparse
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
from tqdm import tqdm

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("⚠️  sentence-transformers not installed. Run: uv pip install sentence-transformers")


@dataclass
class SnippetForEmbedding:
    id: str
    name: str
    type: str
    patterns: List[str]
    code: str
    file_path: str
    repo_id: str


def load_snippets(snippets_dir: Path) -> List[SnippetForEmbedding]:
    """Load all snippets from JSONL file."""
    snippets = []
    snippets_file = snippets_dir / "all_snippets.jsonl"

    if not snippets_file.exists():
        print(f"❌ Snippets file not found: {snippets_file}")
        return snippets

    with open(snippets_file) as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                snippets.append(SnippetForEmbedding(
                    id=data["id"],
                    name=data["name"],
                    type=data["type"],
                    patterns=data.get("patterns", []),
                    code=data["code"],
                    file_path=data.get("file_path", ""),
                    repo_id=data.get("repo_id", ""),
                ))

    return snippets


def create_embedding_text(snippet: SnippetForEmbedding) -> str:
    """
    Create text representation for embedding.

    Combines:
    - Name (important for semantic matching)
    - Type (widget, service, provider, model)
    - Patterns (auth, forms, navigation, etc.)
    - Code (the actual implementation)

    The embedding captures both the "what" (name, type, patterns)
    and the "how" (actual code implementation).
    """
    parts = []

    # Name with type context
    parts.append(f"{snippet.type}: {snippet.name}")

    # Patterns as tags
    if snippet.patterns:
        parts.append(f"patterns: {', '.join(snippet.patterns)}")

    # Code (truncated to avoid too long embeddings)
    # Most embedding models have a token limit (~512 tokens)
    code_preview = snippet.code[:1500]  # ~375 tokens roughly
    parts.append(f"code:\n{code_preview}")

    return "\n".join(parts)


def embed_snippets(
    snippets: List[SnippetForEmbedding],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> tuple[np.ndarray, List[str]]:
    """
    Generate embeddings for all snippets.

    Args:
        snippets: List of snippets to embed
        model_name: Sentence transformer model to use
        batch_size: Batch size for encoding

    Returns:
        Tuple of (embeddings array, list of snippet IDs)
    """
    print(f"📦 Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    # Create texts for embedding
    print("📝 Preparing texts for embedding...")
    texts = [create_embedding_text(s) for s in snippets]
    ids = [s.id for s in snippets]

    # Generate embeddings
    print(f"🔢 Generating embeddings for {len(texts)} snippets...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # For cosine similarity
    )

    return embeddings, ids


def save_embeddings(
    embeddings: np.ndarray,
    ids: List[str],
    snippets: List[SnippetForEmbedding],
    output_dir: Path,
    model_name: str,
):
    """Save embeddings and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save embeddings as numpy array
    embeddings_file = output_dir / "snippet_embeddings.npy"
    np.save(embeddings_file, embeddings)
    print(f"💾 Saved embeddings: {embeddings_file} ({embeddings.shape})")

    # Save ID mapping and metadata
    metadata = {
        "model": model_name,
        "embedding_dim": int(embeddings.shape[1]),
        "num_snippets": len(ids),
        "ids": ids,
        "snippets": [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "patterns": s.patterns,
                "repo_id": s.repo_id,
            }
            for s in snippets
        ],
    }

    metadata_file = output_dir / "embedding_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"💾 Saved metadata: {metadata_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for code snippets")
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence transformer model (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for encoding (default: 32)",
    )
    parser.add_argument(
        "--snippets-dir",
        type=Path,
        default=None,
        help="Path to snippets directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to output directory",
    )

    args = parser.parse_args()

    if not HAS_SENTENCE_TRANSFORMERS:
        print("❌ Please install sentence-transformers first:")
        print("   uv pip install sentence-transformers")
        return

    # Set paths
    project_root = Path(__file__).parent.parent
    snippets_dir = args.snippets_dir or project_root / "curated" / "snippets"
    output_dir = args.output_dir or project_root / "curated" / "embeddings"

    print(f"\n{'='*60}")
    print("🔢 ClawForge Embedding Generator")
    print(f"{'='*60}")
    print(f"Model: {args.model}")
    print(f"Snippets: {snippets_dir}")
    print(f"Output: {output_dir}")
    print()

    # Load snippets
    print("📂 Loading snippets...")
    snippets = load_snippets(snippets_dir)
    print(f"   Loaded {len(snippets)} snippets")

    if not snippets:
        print("❌ No snippets found!")
        return

    # Generate embeddings
    embeddings, ids = embed_snippets(
        snippets,
        model_name=args.model,
        batch_size=args.batch_size,
    )

    # Save
    save_embeddings(embeddings, ids, snippets, output_dir, args.model)

    print(f"\n{'='*60}")
    print("✅ EMBEDDING COMPLETE")
    print(f"{'='*60}")
    print(f"   Snippets: {len(snippets)}")
    print(f"   Embedding dim: {embeddings.shape[1]}")
    print(f"   Total size: {embeddings.nbytes / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
