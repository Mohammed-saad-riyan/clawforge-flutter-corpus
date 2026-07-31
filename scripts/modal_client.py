#!/usr/bin/env python3
"""
Modal API client for Qwen 2.5 Coder.

Supports both the simple ClawForge endpoint and OpenAI-compatible endpoint.

Usage:
    from modal_client import ModalClient

    client = ModalClient()
    response = client.generate(prompt="Build a login screen", system="You are a Flutter expert")
"""

import os
import json
import httpx
from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class GenerationResponse:
    text: str
    tokens_used: int
    cost_cents: float
    model: str = "qwen2.5-coder-7b"


@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str


class ModalClient:
    """Client for calling Qwen 2.5 Coder on Modal."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        openai_url: Optional[str] = None,
        timeout: float = 300.0,  # 5 minutes for cold starts
    ):
        """
        Initialize Modal client.

        Args:
            base_url: ClawForge simple endpoint URL
            openai_url: OpenAI-compatible endpoint URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "MODAL_CLAWFORGE_URL",
            "https://mohammed-saad-riyan--clawforge-llm-generate.modal.run"
        )
        self.openai_url = openai_url or os.getenv(
            "MODAL_OPENAI_URL",
            "https://mohammed-saad-riyan--clawforge-llm-v1-chat-completions.modal.run"
        )
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.2,
        retries: int = 2,
    ) -> GenerationResponse:
        """
        Generate code using the simple ClawForge endpoint.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            retries: Number of retries for timeouts (Modal cold starts)

        Returns:
            GenerationResponse with generated text
        """
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        last_error = None
        for attempt in range(retries + 1):
            try:
                if attempt > 0:
                    print(f"   ⏳ Retry {attempt}/{retries} (Modal may be cold starting)...")

                response = self._client.post(
                    self.base_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                data = response.json()
                return GenerationResponse(
                    text=data.get("text", ""),
                    tokens_used=data.get("tokens_used", 0),
                    cost_cents=data.get("cost_cents", 0.0),
                )
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < retries:
                    continue
                raise
            except Exception as e:
                last_error = e
                raise

        raise last_error

    def chat(
        self,
        messages: List[Message],
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> GenerationResponse:
        """
        Generate using OpenAI-compatible chat completions.

        Args:
            messages: List of Message objects
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            GenerationResponse with generated text
        """
        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = self._client.post(
            self.openai_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = response.json()

        # Extract text from OpenAI format
        text = ""
        if "choices" in data and len(data["choices"]) > 0:
            text = data["choices"][0].get("message", {}).get("content", "")

        return GenerationResponse(
            text=text,
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            cost_cents=0.0,  # OpenAI endpoint doesn't return cost
        )

    def generate_flutter(
        self,
        user_prompt: str,
        template_context: Optional[str] = None,
        knowledge_context: Optional[str] = None,
        max_tokens: int = 8192,
    ) -> GenerationResponse:
        """
        Generate Flutter code with template and knowledge context.

        This is the main entry point for the ClawForge pipeline.

        Args:
            user_prompt: What the user wants to build
            template_context: YAML template for the app type
            knowledge_context: Retrieved widgets, patterns, examples
            max_tokens: Maximum tokens to generate

        Returns:
            GenerationResponse with generated Flutter code
        """
        system_prompt = self._build_system_prompt(template_context, knowledge_context)

        return self.generate(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=0.2,  # Low temperature for code generation
        )

    def _build_system_prompt(
        self,
        template_context: Optional[str] = None,
        knowledge_context: Optional[str] = None,
    ) -> str:
        """Build the system prompt with all context."""
        parts = [
            "You are an expert Flutter developer. Generate production-ready, clean architecture Flutter code.",
            "",
            "RULES:",
            "- Use Riverpod for state management",
            "- Use GoRouter for navigation",
            "- Follow clean architecture (features/domain/data/presentation)",
            "- Use freezed for immutable models",
            "- Handle loading, error, and empty states",
            "- Include proper error handling",
            "- Write type-safe code with no dynamic types",
            "- Generate complete, runnable code",
            "",
        ]

        if template_context:
            parts.append("APPLICATION TEMPLATE:")
            parts.append("```yaml")
            parts.append(template_context)
            parts.append("```")
            parts.append("")

        if knowledge_context:
            parts.append("REFERENCE PATTERNS AND COMPONENTS:")
            parts.append(knowledge_context)
            parts.append("")

        parts.append("Generate the complete Flutter application code.")

        return "\n".join(parts)

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Convenience function for simple usage
def generate(prompt: str, **kwargs) -> GenerationResponse:
    """Quick generate without managing client lifecycle."""
    with ModalClient() as client:
        return client.generate(prompt, **kwargs)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python modal_client.py '<prompt>'")
        print("Example: python modal_client.py 'Write a Flutter login screen with Riverpod'")
        sys.exit(1)

    prompt = sys.argv[1]
    print(f"🚀 Generating for: {prompt}\n")

    try:
        response = generate(prompt)
        print(f"📝 Generated ({response.tokens_used} tokens):\n")
        print(response.text)
        print(f"\n💰 Cost: ${response.cost_cents/100:.4f}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
