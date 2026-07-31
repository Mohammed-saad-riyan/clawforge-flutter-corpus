#!/usr/bin/env python3
"""
ClawForge Flutter Generator - Main generation pipeline.

Pipeline:
1. User prompt → Template matcher (rule-based, fast)
2. Template → Knowledge retriever (widgets, patterns, packages)
3. Template → Snippet retriever (actual code implementations)
4. Context assembly (template + knowledge + code snippets)
5. Modal/Qwen 2.5 Coder → Generated code
6. (Future) Validation → Repair loop

Usage:
    python scripts/generate.py "Build a food delivery app"
    python scripts/generate.py --interactive

Environment:
    MODAL_CLAWFORGE_URL: Modal endpoint URL (optional, has default)
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

# Import our modules
from match_template import match_template, TemplateMatch
from knowledge_retriever import KnowledgeRetriever, RetrievalResult
from snippet_retriever import SnippetRetriever, Snippet
from modal_client import ModalClient, GenerationResponse


@dataclass
class GenerationResult:
    prompt: str
    template: TemplateMatch
    knowledge: RetrievalResult
    snippets: List[Snippet]
    response: GenerationResponse
    generated_at: str

    def save(self, output_dir: Path):
        """Save generation result to files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save metadata
        metadata = {
            "prompt": self.prompt,
            "template_name": self.template.name,
            "template_score": self.template.score,
            "tokens_used": self.response.tokens_used,
            "cost_cents": self.response.cost_cents,
            "generated_at": self.generated_at,
            "packages": self.knowledge.packages,
            "patterns": [p.name for p in self.knowledge.patterns],
            "snippets_used": [{"name": s.name, "type": s.type, "patterns": s.patterns} for s in self.snippets],
        }
        with open(output_dir / f"{timestamp}_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Save generated code
        with open(output_dir / f"{timestamp}_generated.dart", "w") as f:
            f.write(self.response.text)

        print(f"💾 Saved to: {output_dir / timestamp}_*")


class ClawForgeGenerator:
    """Main ClawForge generation pipeline."""

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        knowledge_dir: Optional[Path] = None,
        snippets_dir: Optional[Path] = None,
    ):
        """
        Initialize the generator.

        Args:
            templates_dir: Path to templates directory
            knowledge_dir: Path to curated/extracted directory
            snippets_dir: Path to curated/snippets directory
        """
        project_root = Path(__file__).parent.parent
        self.templates_dir = templates_dir or project_root / "templates"
        self.knowledge_dir = knowledge_dir or project_root / "curated" / "extracted"
        self.snippets_dir = snippets_dir or project_root / "curated" / "snippets"
        self.output_dir = project_root / "output"

        # Load components
        self.retriever = KnowledgeRetriever(self.knowledge_dir)
        self.snippet_retriever = SnippetRetriever(self.snippets_dir)
        self.client = ModalClient()

        # Load templates
        with open(self.templates_dir / "template_registry.yaml") as f:
            data = yaml.safe_load(f)
        # Handle both formats: list or dict with "templates" key
        if isinstance(data, dict) and "templates" in data:
            self.templates = data["templates"]
        else:
            self.templates = data
        self.template_map = {t["name"]: t for t in self.templates}

    def generate(
        self,
        user_prompt: str,
        max_tokens: int = 8192,
        verbose: bool = True,
    ) -> GenerationResult:
        """
        Generate Flutter code from a user prompt.

        Args:
            user_prompt: What the user wants to build
            max_tokens: Maximum tokens to generate
            verbose: Print progress

        Returns:
            GenerationResult with all context and generated code
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"🚀 ClawForge Generator")
            print(f"{'='*60}")
            print(f"\n📝 Prompt: {user_prompt}\n")

        # Step 1: Match template
        if verbose:
            print("1️⃣  Matching template...")

        template_match = match_template(user_prompt)

        if verbose:
            print(f"   ✅ Matched: {template_match.name} (score: {template_match.score})")

        # Get full template
        template = self.template_map.get(template_match.name, {})

        # Step 2: Retrieve knowledge (metadata)
        if verbose:
            print("\n2️⃣  Retrieving knowledge...")

        knowledge = self.retriever.retrieve_for_template(template, user_prompt)

        if verbose:
            print(f"   ✅ Widgets: {len(knowledge.widgets)}")
            print(f"   ✅ Patterns: {len(knowledge.patterns)}")
            print(f"   ✅ Packages: {len(knowledge.packages)}")

        # Step 3: Retrieve code snippets (actual implementations)
        if verbose:
            print("\n3️⃣  Retrieving code snippets...")

        snippets = self.snippet_retriever.retrieve_for_template(
            template,
            user_prompt,
            max_snippets=8,
            max_chars=12000,
        )

        if verbose:
            print(f"   ✅ Snippets: {len(snippets)}")
            for s in snippets[:5]:
                print(f"      - {s.name} ({s.type}) [{s.lines} lines]")
            if len(snippets) > 5:
                print(f"      ... and {len(snippets) - 5} more")

        # Step 4: Build context
        if verbose:
            print("\n4️⃣  Assembling context...")

        template_yaml = yaml.dump(template, default_flow_style=False)
        knowledge_context = knowledge.to_context_string()
        snippet_context = self.snippet_retriever.to_context_string(snippets)

        # Combine knowledge and snippets
        full_context = f"{knowledge_context}\n\n{snippet_context}"

        if verbose:
            print(f"   ✅ Template context: {len(template_yaml)} chars")
            print(f"   ✅ Knowledge context: {len(knowledge_context)} chars")
            print(f"   ✅ Snippet context: {len(snippet_context)} chars")
            print(f"   ✅ Total context: {len(full_context)} chars")

        # Step 5: Generate code
        if verbose:
            print("\n5️⃣  Generating code (this may take a moment)...")

        response = self.client.generate_flutter(
            user_prompt=user_prompt,
            template_context=template_yaml,
            knowledge_context=full_context,
            max_tokens=max_tokens,
        )

        if verbose:
            print(f"   ✅ Generated: {response.tokens_used} tokens")
            print(f"   ✅ Cost: ${response.cost_cents/100:.4f}")

        # Create result
        result = GenerationResult(
            prompt=user_prompt,
            template=template_match,
            knowledge=knowledge,
            snippets=snippets,
            response=response,
            generated_at=datetime.now().isoformat(),
        )

        if verbose:
            print(f"\n{'='*60}")
            print("✅ GENERATION COMPLETE")
            print(f"{'='*60}\n")

        return result

    def interactive(self):
        """Run interactive generation session."""
        print("\n" + "="*60)
        print("🦀 ClawForge Interactive Generator")
        print("="*60)
        print("\nEnter your app description (or 'quit' to exit):")
        print("Example: 'Build a food delivery app with restaurant listings'\n")

        while True:
            try:
                user_input = input(">>> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit", "q"):
                    print("\n👋 Goodbye!")
                    break

                # Generate
                result = self.generate(user_input)

                # Show output
                print("\n📄 GENERATED CODE:")
                print("-" * 40)
                print(result.response.text[:2000])
                if len(result.response.text) > 2000:
                    print(f"\n... ({len(result.response.text) - 2000} more characters)")

                # Offer to save
                save = input("\n💾 Save to file? (y/n): ").strip().lower()
                if save == "y":
                    result.save(self.output_dir)

                print()

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Try again or type 'quit' to exit.\n")

    def close(self):
        """Clean up resources."""
        self.client.close()


def main():
    parser = argparse.ArgumentParser(
        description="ClawForge Flutter Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate.py "Build a food delivery app"
    python generate.py --interactive
    python generate.py "Create a fitness tracker" --save
        """
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="App description prompt",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Save output to file",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum tokens to generate (default: 8192)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without calling Modal",
    )

    args = parser.parse_args()

    generator = ClawForgeGenerator()

    try:
        if args.interactive:
            generator.interactive()
        elif args.prompt:
            if args.dry_run:
                # Show what would be sent
                template_match = match_template(args.prompt)
                template = generator.template_map.get(template_match.name, {})
                knowledge = generator.retriever.retrieve_for_template(template, args.prompt)
                snippets = generator.snippet_retriever.retrieve_for_template(
                    template, args.prompt, max_snippets=8, max_chars=12000
                )

                print("\n🔍 DRY RUN - Would send:")
                print(f"\nTemplate: {template_match.name}")
                print(f"Patterns: {[p.name for p in knowledge.patterns]}")
                print(f"Packages: {knowledge.packages[:10]}...")
                print(f"\nSnippets ({len(snippets)}):")
                for s in snippets:
                    print(f"  - {s.name} ({s.type}) [{s.lines} lines] {s.patterns}")
                print(f"\nKnowledge context:\n{knowledge.to_context_string()[:1000]}...")
                print(f"\nSnippet context:\n{generator.snippet_retriever.to_context_string(snippets[:3])[:2000]}...")
            else:
                result = generator.generate(
                    args.prompt,
                    max_tokens=args.max_tokens,
                    verbose=not args.quiet,
                )

                if args.quiet:
                    print(result.response.text)
                else:
                    print("\n📄 GENERATED CODE:")
                    print("-" * 60)
                    print(result.response.text)

                if args.save:
                    result.save(generator.output_dir)
        else:
            parser.print_help()
    finally:
        generator.close()


if __name__ == "__main__":
    main()
