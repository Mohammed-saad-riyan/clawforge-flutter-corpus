"""Rule-based template matching for ClawForge.

Loads templates/template_registry.yaml and returns the best-matching template
based on keyword scoring. This is intentionally deterministic and fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "templates" / "template_registry.yaml"


@dataclass(frozen=True)
class TemplateMatch:
    name: str
    score: int
    template: dict[str, Any]


def load_registry() -> list[dict[str, Any]]:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("templates", [])


def score_template(user_prompt: str, template: dict[str, Any]) -> int:
    prompt = user_prompt.lower()
    score = 0
    for keyword in template.get("keywords", []):
        if keyword.lower() in prompt:
            score += 10
    return score


def match_template(user_prompt: str) -> TemplateMatch:
    templates = load_registry()
    if not templates:
        raise RuntimeError("No templates found in registry")

    best = TemplateMatch(name="BASIC_CRUD", score=-1, template={})
    for template in templates:
        score = score_template(user_prompt, template)
        if score > best.score:
            best = TemplateMatch(
                name=template["name"],
                score=score,
                template=template,
            )

    fallback = next((t for t in templates if t.get("name") == "BASIC_CRUD"), templates[0])
    if best.score <= 5:
        return TemplateMatch(name=fallback["name"], score=best.score, template=fallback)
    return best


if __name__ == "__main__":
    import sys

    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        raise SystemExit("usage: python scripts/match_template.py <prompt>")
    match = match_template(prompt)
    print(match.name)
    print(match.score)
