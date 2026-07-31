#!/usr/bin/env python3
"""
Dart AST Extractor - Extract structured knowledge from Dart/Flutter files.

Extracts:
- Classes (with inheritance, mixins, interfaces)
- Widgets (StatelessWidget, StatefulWidget, ConsumerWidget, etc.)
- Providers (StateNotifier, ChangeNotifier, Riverpod providers)
- Methods and their signatures
- Imports and dependencies
- Package dependencies from pubspec.yaml

Usage:
    python scripts/dart_ast_extractor.py <dart_file_or_directory>
    python scripts/dart_ast_extractor.py raw/github/S002
"""

import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Set
import yaml


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Import:
    path: str
    is_package: bool
    alias: Optional[str] = None
    show: List[str] = field(default_factory=list)
    hide: List[str] = field(default_factory=list)


@dataclass
class Method:
    name: str
    return_type: Optional[str]
    parameters: List[str]
    is_async: bool
    is_static: bool
    is_override: bool
    line_number: int


@dataclass
class DartClass:
    name: str
    file_path: str
    line_number: int
    extends: Optional[str] = None
    implements: List[str] = field(default_factory=list)
    mixins: List[str] = field(default_factory=list)
    methods: List[Method] = field(default_factory=list)
    is_abstract: bool = False
    # Flutter-specific
    is_widget: bool = False
    widget_type: Optional[str] = None  # Stateless, Stateful, Consumer, etc.
    is_provider: bool = False
    provider_type: Optional[str] = None  # StateNotifier, ChangeNotifier, etc.
    is_state: bool = False  # State<T> class


@dataclass
class DartFile:
    path: str
    imports: List[Import] = field(default_factory=list)
    classes: List[DartClass] = field(default_factory=list)
    top_level_functions: List[Method] = field(default_factory=list)
    # Detected patterns
    packages_used: Set[str] = field(default_factory=set)
    patterns_detected: List[str] = field(default_factory=list)


@dataclass
class ProjectMetadata:
    name: str
    path: str
    description: Optional[str] = None
    packages: Dict[str, str] = field(default_factory=dict)  # name -> version
    dev_packages: Dict[str, str] = field(default_factory=dict)
    flutter_version: Optional[str] = None
    dart_sdk: Optional[str] = None


# ============================================================================
# Patterns for Detection
# ============================================================================

WIDGET_TYPES = {
    "StatelessWidget": "stateless",
    "StatefulWidget": "stateful",
    "State": "state",
    "ConsumerWidget": "consumer",
    "ConsumerStatefulWidget": "consumer_stateful",
    "HookWidget": "hook",
    "HookConsumerWidget": "hook_consumer",
}

PROVIDER_TYPES = {
    "StateNotifier": "state_notifier",
    "ChangeNotifier": "change_notifier",
    "AsyncNotifier": "async_notifier",
    "Notifier": "notifier",
    "FamilyNotifier": "family_notifier",
    "StreamNotifier": "stream_notifier",
}

ARCHITECTURE_PATTERNS = {
    "repository": ["Repository", "RepositoryImpl", "DataSource"],
    "usecase": ["UseCase", "Interactor"],
    "bloc": ["Bloc", "Cubit", "Event", "State"],
    "service": ["Service", "ApiService", "AuthService"],
    "controller": ["Controller", "GetxController"],
    "viewmodel": ["ViewModel", "ViewState"],
}


# ============================================================================
# Regex Patterns
# ============================================================================

# Import patterns
IMPORT_PATTERN = re.compile(
    r"import\s+['\"]([^'\"]+)['\"]\s*"
    r"(?:as\s+(\w+)\s*)?"
    r"(?:show\s+([\w,\s]+)\s*)?"
    r"(?:hide\s+([\w,\s]+)\s*)?;"
)

# Class definition pattern (handles multiline)
CLASS_PATTERN = re.compile(
    r"(abstract\s+)?class\s+(\w+)"
    r"(?:<[^>]+>)?\s*"  # Generic parameters
    r"(?:extends\s+([\w<>,\s]+?))?\s*"  # Extends
    r"(?:with\s+([\w<>,\s]+?))?\s*"  # Mixins
    r"(?:implements\s+([\w<>,\s]+?))?\s*"  # Implements
    r"\{",
    re.MULTILINE
)

# Method pattern
METHOD_PATTERN = re.compile(
    r"(@override\s+)?"
    r"(static\s+)?"
    r"([\w<>?,\s]+?)\s+"  # Return type
    r"(\w+)\s*"  # Method name
    r"\(([^)]*)\)\s*"  # Parameters
    r"(async\s*)?"  # Async modifier
    r"[{\n;]",
    re.MULTILINE
)

# Provider declaration patterns
PROVIDER_DECL_PATTERN = re.compile(
    r"final\s+(\w+)\s*=\s*"
    r"(StateNotifierProvider|ChangeNotifierProvider|Provider|FutureProvider|StreamProvider|NotifierProvider)"
    r"(?:<[^>]+>)?\s*\("
)

# Riverpod 2.0 annotation pattern
RIVERPOD_ANNOTATION = re.compile(r"@riverpod\s*\n")


# ============================================================================
# Extraction Functions
# ============================================================================

def extract_imports(content: str) -> List[Import]:
    """Extract all imports from Dart file content."""
    imports = []
    for match in IMPORT_PATTERN.finditer(content):
        path = match.group(1)
        alias = match.group(2)
        show = [s.strip() for s in match.group(3).split(",")] if match.group(3) else []
        hide = [s.strip() for s in match.group(4).split(",")] if match.group(4) else []

        imports.append(Import(
            path=path,
            is_package=path.startswith("package:"),
            alias=alias,
            show=show,
            hide=hide,
        ))
    return imports


def extract_classes(content: str, file_path: str) -> List[DartClass]:
    """Extract all class definitions from Dart file content."""
    classes = []
    lines = content.split("\n")

    for match in CLASS_PATTERN.finditer(content):
        # Calculate line number
        line_number = content[:match.start()].count("\n") + 1

        is_abstract = match.group(1) is not None
        name = match.group(2)
        extends = match.group(3).strip() if match.group(3) else None
        mixins_str = match.group(4)
        implements_str = match.group(5)

        mixins = [m.strip() for m in mixins_str.split(",")] if mixins_str else []
        implements = [i.strip() for i in implements_str.split(",")] if implements_str else []

        # Detect widget type
        is_widget = False
        widget_type = None
        if extends:
            base_class = extends.split("<")[0].strip()
            if base_class in WIDGET_TYPES:
                is_widget = True
                widget_type = WIDGET_TYPES[base_class]

        # Detect provider type
        is_provider = False
        provider_type = None
        if extends:
            base_class = extends.split("<")[0].strip()
            if base_class in PROVIDER_TYPES:
                is_provider = True
                provider_type = PROVIDER_TYPES[base_class]

        # Detect State class
        is_state = extends and extends.startswith("State<")

        dart_class = DartClass(
            name=name,
            file_path=file_path,
            line_number=line_number,
            extends=extends,
            implements=implements,
            mixins=mixins,
            is_abstract=is_abstract,
            is_widget=is_widget,
            widget_type=widget_type,
            is_provider=is_provider,
            provider_type=provider_type,
            is_state=is_state,
        )

        classes.append(dart_class)

    return classes


def extract_packages_from_imports(imports: List[Import]) -> Set[str]:
    """Extract package names from import statements."""
    packages = set()
    for imp in imports:
        if imp.is_package:
            # Extract package name from "package:name/..."
            parts = imp.path.replace("package:", "").split("/")
            if parts:
                packages.add(parts[0])
    return packages


def detect_patterns(classes: List[DartClass], imports: List[Import]) -> List[str]:
    """Detect architectural patterns in the file."""
    patterns = []
    class_names = [c.name for c in classes]

    for pattern_name, indicators in ARCHITECTURE_PATTERNS.items():
        for indicator in indicators:
            for class_name in class_names:
                if indicator in class_name:
                    if pattern_name not in patterns:
                        patterns.append(pattern_name)
                    break

    # Check imports for patterns
    import_str = " ".join(i.path for i in imports)
    if "riverpod" in import_str:
        if "riverpod" not in patterns:
            patterns.append("riverpod")
    if "bloc" in import_str or "flutter_bloc" in import_str:
        if "bloc" not in patterns:
            patterns.append("bloc")
    if "go_router" in import_str:
        if "go_router" not in patterns:
            patterns.append("go_router")
    if "dio" in import_str:
        if "dio" not in patterns:
            patterns.append("dio")
    if "hive" in import_str:
        if "hive" not in patterns:
            patterns.append("hive")
    if "freezed" in import_str:
        if "freezed" not in patterns:
            patterns.append("freezed")

    return patterns


def parse_dart_file(file_path: Path) -> Optional[DartFile]:
    """Parse a single Dart file and extract structured information."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️  Could not read {file_path}: {e}")
        return None

    imports = extract_imports(content)
    classes = extract_classes(content, str(file_path))
    packages = extract_packages_from_imports(imports)
    patterns = detect_patterns(classes, imports)

    return DartFile(
        path=str(file_path),
        imports=imports,
        classes=classes,
        packages_used=packages,
        patterns_detected=patterns,
    )


def parse_pubspec(pubspec_path: Path) -> Optional[ProjectMetadata]:
    """Parse pubspec.yaml to extract project metadata."""
    try:
        content = pubspec_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except Exception as e:
        print(f"  ⚠️  Could not parse {pubspec_path}: {e}")
        return None

    if not data:
        return None

    # Extract dependencies
    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("dev_dependencies", {}) or {}

    # Normalize version strings
    def normalize_version(v):
        if isinstance(v, dict):
            return str(v.get("version", "git/path"))
        return str(v) if v else "any"

    packages = {k: normalize_version(v) for k, v in deps.items() if k != "flutter"}
    dev_packages = {k: normalize_version(v) for k, v in dev_deps.items()}

    # Extract SDK constraints
    env = data.get("environment", {}) or {}
    dart_sdk = env.get("sdk")
    flutter_version = deps.get("flutter", {})
    if isinstance(flutter_version, dict):
        flutter_version = flutter_version.get("sdk")

    return ProjectMetadata(
        name=data.get("name", "unknown"),
        path=str(pubspec_path.parent),
        description=data.get("description"),
        packages=packages,
        dev_packages=dev_packages,
        dart_sdk=dart_sdk,
        flutter_version=str(flutter_version) if flutter_version else None,
    )


# ============================================================================
# Main Processing
# ============================================================================

def process_directory(dir_path: Path, output_path: Optional[Path] = None) -> Dict:
    """Process all Dart files in a directory and extract knowledge."""
    results = {
        "project": None,
        "files": [],
        "summary": {
            "total_files": 0,
            "total_classes": 0,
            "total_widgets": 0,
            "total_providers": 0,
            "packages_used": set(),
            "patterns_detected": set(),
            "widget_types": {},
            "provider_types": {},
        }
    }

    # Parse pubspec if exists
    pubspec_path = dir_path / "pubspec.yaml"
    if pubspec_path.exists():
        results["project"] = parse_pubspec(pubspec_path)
        if results["project"]:
            print(f"  📦 Project: {results['project'].name}")

    # Find all Dart files
    dart_files = list(dir_path.rglob("*.dart"))
    print(f"  📄 Found {len(dart_files)} Dart files")

    # Process each file
    for dart_file in dart_files:
        # Skip generated files
        if ".g.dart" in dart_file.name or ".freezed.dart" in dart_file.name:
            continue

        parsed = parse_dart_file(dart_file)
        if parsed:
            results["files"].append(parsed)

            # Update summary
            results["summary"]["total_files"] += 1
            results["summary"]["total_classes"] += len(parsed.classes)
            results["summary"]["packages_used"].update(parsed.packages_used)
            results["summary"]["patterns_detected"].update(parsed.patterns_detected)

            for cls in parsed.classes:
                if cls.is_widget:
                    results["summary"]["total_widgets"] += 1
                    wt = cls.widget_type or "unknown"
                    results["summary"]["widget_types"][wt] = results["summary"]["widget_types"].get(wt, 0) + 1
                if cls.is_provider:
                    results["summary"]["total_providers"] += 1
                    pt = cls.provider_type or "unknown"
                    results["summary"]["provider_types"][pt] = results["summary"]["provider_types"].get(pt, 0) + 1

    # Convert sets to lists for JSON serialization
    results["summary"]["packages_used"] = sorted(results["summary"]["packages_used"])
    results["summary"]["patterns_detected"] = sorted(results["summary"]["patterns_detected"])

    return results


def serialize_results(results: Dict) -> Dict:
    """Convert results to JSON-serializable format."""
    def convert(obj):
        if isinstance(obj, set):
            return sorted(list(obj))
        if hasattr(obj, "__dataclass_fields__"):
            return {k: convert(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        return obj

    return convert(results)


def main():
    if len(sys.argv) < 2:
        print("Usage: python dart_ast_extractor.py <path>")
        print("  path: Dart file or directory to analyze")
        sys.exit(1)

    target = Path(sys.argv[1])

    if not target.exists():
        print(f"❌ Path not found: {target}")
        sys.exit(1)

    print(f"\n🔍 Analyzing: {target}\n")

    if target.is_file():
        result = parse_dart_file(target)
        if result:
            output = serialize_results(asdict(result))
            print(json.dumps(output, indent=2))
    else:
        results = process_directory(target)
        output = serialize_results(results)

        # Print summary
        summary = results["summary"]
        print(f"\n{'='*50}")
        print(f"📊 EXTRACTION SUMMARY")
        print(f"{'='*50}")
        print(f"  Files analyzed:    {summary['total_files']}")
        print(f"  Classes found:     {summary['total_classes']}")
        print(f"  Widgets found:     {summary['total_widgets']}")
        print(f"  Providers found:   {summary['total_providers']}")
        print(f"  Packages used:     {len(summary['packages_used'])}")
        print(f"  Patterns detected: {', '.join(summary['patterns_detected']) or 'none'}")

        if summary["widget_types"]:
            print(f"\n  Widget Types:")
            for wt, count in sorted(summary["widget_types"].items()):
                print(f"    - {wt}: {count}")

        if summary["provider_types"]:
            print(f"\n  Provider Types:")
            for pt, count in sorted(summary["provider_types"].items()):
                print(f"    - {pt}: {count}")

        print(f"{'='*50}\n")

        # Save to file
        output_file = target / "extracted_knowledge.json"
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        print(f"💾 Saved to: {output_file}")


if __name__ == "__main__":
    main()
