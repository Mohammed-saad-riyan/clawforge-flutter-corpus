#!/usr/bin/env python3
"""
Code Snippet Extractor - Extract complete implementations from Dart files.

Extracts:
- Complete widget implementations (class + build method)
- Service/Repository implementations
- Provider/StateNotifier implementations
- Model classes with freezed/json_serializable
- Common patterns (auth, forms, navigation)

Output: JSONL files with full code snippets for retrieval.

Usage:
    python scripts/extract_snippets.py
    python scripts/extract_snippets.py raw/github/S001
"""

import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Set
from datetime import datetime


@dataclass
class CodeSnippet:
    """A complete code snippet with metadata."""
    id: str
    type: str  # widget, service, provider, model, pattern
    name: str
    code: str
    file_path: str
    repo_id: str
    imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    lines: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


# Patterns for identifying code types
WIDGET_BASES = [
    "StatelessWidget", "StatefulWidget", "State<",
    "ConsumerWidget", "ConsumerStatefulWidget",
    "HookWidget", "HookConsumerWidget",
]

PROVIDER_BASES = [
    "StateNotifier", "ChangeNotifier", "AsyncNotifier",
    "Notifier", "AutoDisposeNotifier",
]

SERVICE_PATTERNS = [
    "Service", "Repository", "DataSource", "Api", "Client",
    "UseCase", "Interactor",
]

MODEL_PATTERNS = [
    "@freezed", "@JsonSerializable", "copyWith", "fromJson", "toJson",
]


def extract_imports(content: str) -> List[str]:
    """Extract import statements from file."""
    imports = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('import '):
            imports.append(line)
        elif line.startswith('export '):
            imports.append(line)
        elif imports and not line.startswith(('import', 'export', '//', '/*', '*', '')):
            break  # End of imports section
    return imports


def extract_class_block(content: str, class_match: re.Match) -> str:
    """Extract the complete class definition including body."""
    start = class_match.start()

    # Find opening brace
    brace_pos = content.find('{', class_match.end())
    if brace_pos == -1:
        return ""

    # Count braces to find matching closing brace
    depth = 1
    pos = brace_pos + 1
    while depth > 0 and pos < len(content):
        char = content[pos]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        pos += 1

    return content[start:pos].strip()


def detect_patterns(code: str, class_name: str) -> List[str]:
    """Detect architectural patterns in the code."""
    patterns = []
    code_lower = code.lower()

    # Auth patterns
    if any(kw in code_lower for kw in ['login', 'signin', 'signup', 'auth', 'logout']):
        patterns.append('auth')

    # Form patterns
    if any(kw in code for kw in ['TextFormField', 'Form(', 'GlobalKey<FormState>', 'validate']):
        patterns.append('forms')

    # Navigation patterns
    if any(kw in code for kw in ['GoRouter', 'context.go(', 'context.push(', 'Navigator.']):
        patterns.append('navigation')

    # State management
    if any(kw in code for kw in ['ref.watch', 'ref.read', 'ConsumerWidget', 'StateNotifier']):
        patterns.append('riverpod')
    if any(kw in code for kw in ['BlocBuilder', 'BlocProvider', 'emit(']):
        patterns.append('bloc')

    # Data patterns
    if any(kw in code for kw in ['Dio', 'http.', 'Response', 'ApiClient']):
        patterns.append('networking')
    if any(kw in code for kw in ['Hive', 'SharedPreferences', 'sqflite']):
        patterns.append('local_storage')

    # UI patterns
    if 'ListView' in code or 'GridView' in code or 'SliverList' in code:
        patterns.append('lists')
    if 'FutureBuilder' in code or 'StreamBuilder' in code:
        patterns.append('async_ui')
    if 'AnimatedContainer' in code or 'AnimationController' in code:
        patterns.append('animations')

    return patterns


def extract_dependencies(code: str, imports: List[str]) -> List[str]:
    """Extract package dependencies from imports."""
    deps = set()
    for imp in imports:
        match = re.search(r"package:(\w+)/", imp)
        if match:
            deps.add(match.group(1))
    return sorted(deps)


def classify_snippet(class_name: str, extends: str, code: str) -> str:
    """Classify the type of snippet."""
    # Check for widgets
    for base in WIDGET_BASES:
        if base in extends:
            return "widget"

    # Check for providers
    for base in PROVIDER_BASES:
        if base in extends:
            return "provider"

    # Check for services/repositories
    for pattern in SERVICE_PATTERNS:
        if pattern in class_name:
            return "service"

    # Check for models
    if any(p in code for p in MODEL_PATTERNS):
        return "model"

    # Default
    return "other"


def extract_snippets_from_file(file_path: Path, repo_id: str) -> List[CodeSnippet]:
    """Extract all code snippets from a Dart file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        return []

    snippets = []
    imports = extract_imports(content)
    dependencies = extract_dependencies(content, imports)

    # Pattern to find class definitions
    class_pattern = re.compile(
        r'(abstract\s+)?class\s+(\w+)(?:<[^>]+>)?\s*'
        r'(?:extends\s+([\w<>,\s]+?))?\s*'
        r'(?:with\s+([\w<>,\s]+?))?\s*'
        r'(?:implements\s+([\w<>,\s]+?))?\s*'
        r'\{',
        re.MULTILINE
    )

    for match in class_pattern.finditer(content):
        is_abstract = match.group(1) is not None
        class_name = match.group(2)
        extends = match.group(3) or ""

        # Skip private classes, generated files, and very small classes
        if class_name.startswith('_'):
            continue
        if '.g.dart' in str(file_path) or '.freezed.dart' in str(file_path):
            continue

        # Extract the full class code
        class_code = extract_class_block(content, match)
        if not class_code:
            continue

        # Skip very short snippets (likely incomplete)
        lines = class_code.count('\n') + 1
        if lines < 5:
            continue

        # Skip very long snippets (likely entire files, not useful)
        if lines > 300:
            continue

        # Classify the snippet
        snippet_type = classify_snippet(class_name, extends, class_code)

        # Skip 'other' type unless it's interesting
        if snippet_type == "other":
            continue

        # Detect patterns
        patterns = detect_patterns(class_code, class_name)

        # Create snippet ID
        snippet_id = f"{repo_id}_{file_path.stem}_{class_name}"

        snippet = CodeSnippet(
            id=snippet_id,
            type=snippet_type,
            name=class_name,
            code=class_code,
            file_path=str(file_path),
            repo_id=repo_id,
            imports=imports[:10],  # Limit imports
            dependencies=dependencies,
            patterns=patterns,
            lines=lines,
        )
        snippets.append(snippet)

    return snippets


def extract_from_repo(repo_path: Path) -> List[CodeSnippet]:
    """Extract all snippets from a repository."""
    repo_id = repo_path.name
    snippets = []

    # Find all Dart files
    dart_files = list(repo_path.rglob("*.dart"))

    for dart_file in dart_files:
        # Skip generated files
        if '.g.dart' in dart_file.name or '.freezed.dart' in dart_file.name:
            continue
        # Skip test files for now
        if '/test/' in str(dart_file) or '_test.dart' in dart_file.name:
            continue

        file_snippets = extract_snippets_from_file(dart_file, repo_id)
        snippets.extend(file_snippets)

    return snippets


def save_snippets(snippets: List[CodeSnippet], output_path: Path):
    """Save snippets to JSONL file."""
    with open(output_path, 'w') as f:
        for snippet in snippets:
            f.write(json.dumps(snippet.to_dict()) + '\n')


def create_snippet_index(snippets: List[CodeSnippet], output_path: Path):
    """Create an index file for quick lookups."""
    index = {
        "total_snippets": len(snippets),
        "by_type": {},
        "by_pattern": {},
        "by_repo": {},
    }

    for s in snippets:
        # By type
        if s.type not in index["by_type"]:
            index["by_type"][s.type] = []
        index["by_type"][s.type].append(s.id)

        # By pattern
        for p in s.patterns:
            if p not in index["by_pattern"]:
                index["by_pattern"][p] = []
            index["by_pattern"][p].append(s.id)

        # By repo
        if s.repo_id not in index["by_repo"]:
            index["by_repo"][s.repo_id] = []
        index["by_repo"][s.repo_id].append(s.id)

    # Convert lists to counts for summary
    summary = {
        "total_snippets": len(snippets),
        "by_type": {k: len(v) for k, v in index["by_type"].items()},
        "by_pattern": {k: len(v) for k, v in index["by_pattern"].items()},
        "repos_with_snippets": len(index["by_repo"]),
    }

    with open(output_path, 'w') as f:
        json.dump({"summary": summary, "index": index}, f, indent=2)

    return summary


def main():
    project_root = Path(__file__).parent.parent
    raw_github = project_root / "raw" / "github"
    output_dir = project_root / "curated" / "snippets"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for specific repo argument
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_dir():
            repos = [target]
        else:
            print(f"❌ Not a directory: {target}")
            sys.exit(1)
    else:
        repos = sorted([d for d in raw_github.iterdir() if d.is_dir()])

    print(f"\n🔍 Extracting code snippets from {len(repos)} repositories\n")

    all_snippets = []

    for repo_path in repos:
        print(f"  📂 {repo_path.name}...", end=" ", flush=True)
        snippets = extract_from_repo(repo_path)
        all_snippets.extend(snippets)
        print(f"{len(snippets)} snippets")

    # Save all snippets
    snippets_file = output_dir / "all_snippets.jsonl"
    save_snippets(all_snippets, snippets_file)

    # Create index
    index_file = output_dir / "snippet_index.json"
    summary = create_snippet_index(all_snippets, index_file)

    # Save by type for faster loading
    for snippet_type in summary["by_type"]:
        type_snippets = [s for s in all_snippets if s.type == snippet_type]
        type_file = output_dir / f"{snippet_type}_snippets.jsonl"
        save_snippets(type_snippets, type_file)

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total snippets: {summary['total_snippets']}")
    print(f"\n  By Type:")
    for t, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
        print(f"    {t}: {count}")
    print(f"\n  By Pattern:")
    for p, count in sorted(summary['by_pattern'].items(), key=lambda x: -x[1]):
        print(f"    {p}: {count}")
    print(f"\n  Output: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
