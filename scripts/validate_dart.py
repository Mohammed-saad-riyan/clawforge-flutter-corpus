#!/usr/bin/env python3
"""
Validate generated Dart code for syntax errors.

Extracts Dart code blocks from generated output and validates them.

Usage:
    python scripts/validate_dart.py output/20260731_200054_generated.dart
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_dart_blocks(content: str) -> list[tuple[str, str]]:
    """Extract Dart code blocks from markdown-style output."""
    pattern = r"```dart\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    blocks = []
    for i, code in enumerate(matches):
        # Try to identify the file name from comments or preceding text
        blocks.append((f"block_{i}.dart", code.strip()))

    return blocks


def validate_dart_syntax(code: str, filename: str = "temp.dart") -> tuple[bool, str]:
    """Validate Dart code syntax using dart format (checks parsing only)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dart', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        # Use dart format to check syntax - it parses the file without resolving imports
        result = subprocess.run(
            ["dart", "format", "--output=none", temp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # dart format returns 0 if the file is valid syntax
        # It will fail with syntax errors but NOT with missing imports
        if result.returncode == 0:
            return True, "Syntax OK"

        # Check for actual syntax errors vs formatting issues
        output = result.stderr + result.stdout
        if "Could not format" in output or "Error" in output:
            return False, output

        return True, "Syntax OK"
    except subprocess.TimeoutExpired:
        return False, "Validation timed out"
    except Exception as e:
        return False, str(e)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def validate_file(file_path: Path) -> dict:
    """Validate a generated Dart file."""
    content = file_path.read_text()
    blocks = extract_dart_blocks(content)

    results = {
        "file": str(file_path),
        "total_blocks": len(blocks),
        "valid_blocks": 0,
        "invalid_blocks": 0,
        "errors": [],
    }

    for filename, code in blocks:
        # Skip very short blocks (likely examples or fragments)
        if len(code.strip()) < 20:
            continue

        is_valid, output = validate_dart_syntax(code, filename)

        if is_valid:
            results["valid_blocks"] += 1
        else:
            results["invalid_blocks"] += 1
            # Extract just the error messages
            error_lines = [l for l in output.split('\n') if 'error' in l.lower()]
            results["errors"].append({
                "block": filename,
                "errors": error_lines[:5],  # Limit to 5 errors per block
            })

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_dart.py <generated_file.dart>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    print(f"\n🔍 Validating: {file_path.name}\n")

    results = validate_file(file_path)

    print(f"📊 VALIDATION RESULTS")
    print(f"{'='*50}")
    print(f"  Total code blocks: {results['total_blocks']}")
    print(f"  ✅ Valid:          {results['valid_blocks']}")
    print(f"  ❌ Invalid:        {results['invalid_blocks']}")

    if results['errors']:
        print(f"\n⚠️  ERRORS FOUND:")
        for err in results['errors']:
            print(f"\n  Block: {err['block']}")
            for e in err['errors']:
                print(f"    - {e}")
    else:
        print(f"\n✅ All code blocks passed syntax validation!")

    print(f"{'='*50}\n")

    return 0 if results['invalid_blocks'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
