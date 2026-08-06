#!/usr/bin/env python3
"""
Flutter Project Scaffolder - Parse model output and create project files.

Parses the model's markdown output containing file markers and code blocks,
then creates a proper Flutter project structure.

Usage:
    from scaffold_project import ProjectScaffolder

    scaffolder = ProjectScaffolder(output_dir="./my_app")
    scaffolder.scaffold_from_text(model_output)
"""

import re
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class ParsedFile:
    """A parsed file from model output."""
    path: str  # Relative path like "lib/main.dart"
    content: str  # File content
    language: str = "dart"  # Language (dart, yaml, etc.)


@dataclass
class ProjectStructure:
    """Parsed project structure."""
    name: str
    files: List[ParsedFile] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)


class OutputParser:
    """
    Parse model output into structured files.

    Handles various formats:
    - ### path/to/file.dart followed by ```dart ... ```
    - ### file.dart (without path)
    - **file.dart** format
    - Project structure comments
    """

    # Patterns for file headers
    FILE_HEADER_PATTERNS = [
        # ### lib/main.dart or ### main.dart
        r'^###\s+(.+?\.(?:dart|yaml|json|md))\s*$',
        # **lib/main.dart** or **main.dart**
        r'^\*\*(.+?\.(?:dart|yaml|json|md))\*\*\s*$',
        # // File: lib/main.dart
        r'^//\s*[Ff]ile:\s*(.+?\.(?:dart|yaml|json|md))\s*$',
    ]

    # Pattern for code blocks
    CODE_BLOCK_PATTERN = r'```(\w+)?\n(.*?)```'

    def __init__(self):
        self.file_patterns = [re.compile(p, re.MULTILINE) for p in self.FILE_HEADER_PATTERNS]
        self.code_block_pattern = re.compile(self.CODE_BLOCK_PATTERN, re.DOTALL)

    def parse(self, text: str) -> ProjectStructure:
        """
        Parse model output into a ProjectStructure.

        Args:
            text: Raw model output text

        Returns:
            ProjectStructure with parsed files
        """
        # Try to extract project name from output
        project_name = self._extract_project_name(text)

        # Parse files
        files = self._parse_files(text)

        # Extract dependencies from pubspec if present
        dependencies, dev_dependencies = self._extract_dependencies(files)

        return ProjectStructure(
            name=project_name,
            files=files,
            dependencies=dependencies,
            dev_dependencies=dev_dependencies,
        )

    def _extract_project_name(self, text: str) -> str:
        """Extract project name from output."""
        # Look for project structure comment
        patterns = [
            r'^```\n?(\w+)/',  # project_name/
            r'Project Structure\s*\n```\n?(\w+)/',
            r'^(\w+)/\s*\n├──',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1)

        return "flutter_app"  # Default

    def _parse_files(self, text: str) -> List[ParsedFile]:
        """Parse all files from the output."""
        files = []

        # Split by potential file headers
        lines = text.split('\n')
        current_file_path = None
        current_content_lines = []
        in_code_block = False
        code_block_lang = "dart"

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for file header
            file_path = self._match_file_header(line)
            if file_path and not in_code_block:
                # Save previous file if exists
                if current_file_path and current_content_lines:
                    content = self._extract_code_content('\n'.join(current_content_lines))
                    if content.strip():
                        files.append(ParsedFile(
                            path=self._normalize_path(current_file_path),
                            content=content,
                            language=self._get_language(current_file_path),
                        ))

                current_file_path = file_path
                current_content_lines = []
                i += 1
                continue

            # Track code blocks
            if line.startswith('```'):
                if in_code_block:
                    in_code_block = False
                else:
                    in_code_block = True
                    # Extract language
                    lang_match = re.match(r'```(\w+)?', line)
                    if lang_match and lang_match.group(1):
                        code_block_lang = lang_match.group(1)

            # Accumulate content for current file
            if current_file_path:
                current_content_lines.append(line)

            i += 1

        # Don't forget the last file
        if current_file_path and current_content_lines:
            content = self._extract_code_content('\n'.join(current_content_lines))
            if content.strip():
                files.append(ParsedFile(
                    path=self._normalize_path(current_file_path),
                    content=content,
                    language=self._get_language(current_file_path),
                ))

        return files

    def _match_file_header(self, line: str) -> Optional[str]:
        """Check if line is a file header, return file path or None."""
        for pattern in self.file_patterns:
            match = pattern.match(line.strip())
            if match:
                return match.group(1)
        return None

    def _extract_code_content(self, text: str) -> str:
        """Extract code from within code blocks."""
        # Find all code blocks
        matches = self.code_block_pattern.findall(text)
        if matches:
            # Return the content of the first/main code block
            return matches[0][1].strip()

        # If no code blocks, return cleaned text
        # Remove markdown formatting
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        return text.strip()

    def _normalize_path(self, path: str) -> str:
        """Normalize file path to proper structure."""
        path = path.strip()

        # Remove leading project name if present (e.g., "food_delivery/lib/main.dart")
        parts = path.split('/')
        if len(parts) > 1 and parts[0] not in ('lib', 'test', 'assets', 'android', 'ios', 'web'):
            # First part might be project name
            if not parts[0].endswith('.dart') and not parts[0].endswith('.yaml'):
                path = '/'.join(parts[1:])

        # Ensure lib/ prefix for dart files if not present
        if path.endswith('.dart') and not path.startswith('lib/') and not path.startswith('test/'):
            # Check if it's a nested path like features/auth/auth.dart
            if '/' in path:
                path = f"lib/{path}"
            else:
                path = f"lib/{path}"

        return path

    def _get_language(self, path: str) -> str:
        """Get language from file extension."""
        if path.endswith('.dart'):
            return 'dart'
        elif path.endswith('.yaml') or path.endswith('.yml'):
            return 'yaml'
        elif path.endswith('.json'):
            return 'json'
        elif path.endswith('.md'):
            return 'markdown'
        return 'text'

    def _extract_dependencies(self, files: List[ParsedFile]) -> Tuple[List[str], List[str]]:
        """Extract dependencies from pubspec.yaml if present."""
        dependencies = []
        dev_dependencies = []

        for f in files:
            if 'pubspec' in f.path:
                # Simple extraction - look for dependency lines
                in_deps = False
                in_dev_deps = False

                for line in f.content.split('\n'):
                    stripped = line.strip()

                    if stripped == 'dependencies:':
                        in_deps = True
                        in_dev_deps = False
                    elif stripped == 'dev_dependencies:':
                        in_deps = False
                        in_dev_deps = True
                    elif stripped and not stripped.startswith('#'):
                        if ':' in stripped and not stripped.endswith(':'):
                            pkg = stripped.split(':')[0].strip()
                            if in_deps and pkg != 'flutter':
                                dependencies.append(pkg)
                            elif in_dev_deps:
                                dev_dependencies.append(pkg)
                        elif stripped and not stripped.startswith('-') and ':' not in stripped:
                            # Reset sections on non-indented lines
                            if not line.startswith(' '):
                                in_deps = False
                                in_dev_deps = False

        return dependencies, dev_dependencies


class ProjectScaffolder:
    """
    Create a Flutter project from parsed output.
    """

    # Default pubspec template
    PUBSPEC_TEMPLATE = '''name: {project_name}
description: A Flutter application generated by ClawForge.
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
{dependencies}

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
{dev_dependencies}

flutter:
  uses-material-design: true
'''

    # Common Flutter dependencies we detect
    COMMON_DEPENDENCIES = {
        'riverpod': 'flutter_riverpod: ^2.4.0',
        'hooks_riverpod': 'hooks_riverpod: ^2.4.0',
        'flutter_hooks': 'flutter_hooks: ^0.20.0',
        'go_router': 'go_router: ^12.0.0',
        'freezed': 'freezed_annotation: ^2.4.0',
        'dio': 'dio: ^5.3.0',
        'shared_preferences': 'shared_preferences: ^2.2.0',
        'cached_network_image': 'cached_network_image: ^3.3.0',
        'shimmer': 'shimmer: ^3.0.0',
        'flutter_bloc': 'flutter_bloc: ^8.1.0',
        'bloc': 'bloc: ^8.1.0',
        'provider': 'provider: ^6.1.0',
        'get_it': 'get_it: ^7.6.0',
        'injectable': 'injectable: ^2.3.0',
        'auto_route': 'auto_route: ^7.8.0',
        'hive': 'hive: ^2.2.0',
        'firebase_core': 'firebase_core: ^2.24.0',
        'firebase_auth': 'firebase_auth: ^4.16.0',
        'cloud_firestore': 'cloud_firestore: ^4.14.0',
        'http': 'http: ^1.1.0',
        'intl': 'intl: ^0.18.0',
        'equatable': 'equatable: ^2.0.0',
        'dartz': 'dartz: ^0.10.0',
        'flutter_svg': 'flutter_svg: ^2.0.0',
        'google_fonts': 'google_fonts: ^6.1.0',
        'flutter_screenutil': 'flutter_screenutil: ^5.9.0',
        'geolocator': 'geolocator: ^10.1.0',
        'google_maps_flutter': 'google_maps_flutter: ^2.5.0',
        'image_picker': 'image_picker: ^1.0.0',
        'url_launcher': 'url_launcher: ^6.2.0',
        'flutter_stripe': 'flutter_stripe: ^10.0.0',
    }

    COMMON_DEV_DEPENDENCIES = {
        'freezed': 'freezed: ^2.4.0',
        'json_serializable': 'json_serializable: ^6.7.0',
        'build_runner': 'build_runner: ^2.4.0',
        'injectable_generator': 'injectable_generator: ^2.4.0',
        'auto_route_generator': 'auto_route_generator: ^7.3.0',
        'hive_generator': 'hive_generator: ^2.0.0',
        'mockito': 'mockito: ^5.4.0',
    }

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize scaffolder.

        Args:
            output_dir: Base directory for generated projects
        """
        project_root = Path(__file__).parent.parent
        self.output_dir = output_dir or project_root / "generated"
        self.parser = OutputParser()

    def scaffold_from_text(
        self,
        text: str,
        project_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Create a Flutter project from model output text.

        Args:
            text: Raw model output
            project_name: Override project name
            overwrite: Overwrite existing project

        Returns:
            Path to generated project
        """
        # Parse output
        structure = self.parser.parse(text)

        if project_name:
            structure.name = project_name

        # Sanitize project name
        structure.name = self._sanitize_name(structure.name)

        # Create project directory
        project_dir = self.output_dir / structure.name

        if project_dir.exists():
            if overwrite:
                shutil.rmtree(project_dir)
            else:
                # Add timestamp to avoid overwriting
                import time
                structure.name = f"{structure.name}_{int(time.time())}"
                project_dir = self.output_dir / structure.name

        project_dir.mkdir(parents=True, exist_ok=True)

        # Detect dependencies from code
        all_code = '\n'.join(f.content for f in structure.files)
        detected_deps = self._detect_dependencies(all_code)
        detected_dev_deps = self._detect_dev_dependencies(all_code)

        # Check if pubspec exists in parsed files
        has_pubspec = any('pubspec' in f.path for f in structure.files)

        # Write files
        files_written = []
        for parsed_file in structure.files:
            file_path = project_dir / parsed_file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'w') as f:
                f.write(parsed_file.content)

            files_written.append(parsed_file.path)

        # Generate pubspec if not present
        if not has_pubspec:
            pubspec_content = self._generate_pubspec(
                structure.name,
                detected_deps,
                detected_dev_deps,
            )
            pubspec_path = project_dir / 'pubspec.yaml'
            with open(pubspec_path, 'w') as f:
                f.write(pubspec_content)
            files_written.append('pubspec.yaml')

        # Generate analysis_options.yaml
        analysis_path = project_dir / 'analysis_options.yaml'
        if not analysis_path.exists():
            with open(analysis_path, 'w') as f:
                f.write('include: package:flutter_lints/flutter.yaml\n')
            files_written.append('analysis_options.yaml')

        # Print summary
        print(f"\n📁 Project created: {project_dir}")
        print(f"   Files: {len(files_written)}")
        for fp in sorted(files_written)[:15]:
            print(f"   - {fp}")
        if len(files_written) > 15:
            print(f"   ... and {len(files_written) - 15} more")

        return project_dir

    def _sanitize_name(self, name: str) -> str:
        """Sanitize project name for valid Flutter package name."""
        # Replace spaces and special chars
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure lowercase
        name = name.lower()
        # Ensure doesn't start with number
        if name and name[0].isdigit():
            name = f"app_{name}"
        return name or "flutter_app"

    def _detect_dependencies(self, code: str) -> List[str]:
        """Detect required dependencies from code imports."""
        deps = []

        for pkg, version in self.COMMON_DEPENDENCIES.items():
            # Check for import statements
            if f"import 'package:{pkg}" in code or f'import "package:{pkg}' in code:
                deps.append(version)
            # Check for package usage patterns
            elif pkg in code.lower():
                deps.append(version)

        return list(set(deps))

    def _detect_dev_dependencies(self, code: str) -> List[str]:
        """Detect required dev dependencies from code."""
        dev_deps = []

        # Freezed detection
        if '@freezed' in code or '@Freezed' in code:
            dev_deps.append(self.COMMON_DEV_DEPENDENCIES['freezed'])
            dev_deps.append(self.COMMON_DEV_DEPENDENCIES['build_runner'])

        # JSON serializable detection
        if '@JsonSerializable' in code or '@jsonSerializable' in code:
            dev_deps.append(self.COMMON_DEV_DEPENDENCIES['json_serializable'])
            dev_deps.append(self.COMMON_DEV_DEPENDENCIES['build_runner'])

        return list(set(dev_deps))

    def _generate_pubspec(
        self,
        project_name: str,
        dependencies: List[str],
        dev_dependencies: List[str],
    ) -> str:
        """Generate pubspec.yaml content."""
        deps_str = '\n'.join(f"  {dep}" for dep in dependencies) if dependencies else ""
        dev_deps_str = '\n'.join(f"  {dep}" for dep in dev_dependencies) if dev_dependencies else ""

        return self.PUBSPEC_TEMPLATE.format(
            project_name=project_name,
            dependencies=deps_str,
            dev_dependencies=dev_deps_str,
        )


def main():
    """Test scaffolder with sample output."""
    # Sample model output
    sample_output = '''
Sure! Here's a Flutter login app:

### Project Structure
```
login_app/
├── lib/
│   ├── main.dart
│   ├── features/
│   │   └── auth/
│   │       ├── login_screen.dart
│   │       └── auth_provider.dart
```

### lib/main.dart
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'features/auth/login_screen.dart';

void main() {
  runApp(
    const ProviderScope(
      child: MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Login App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: const LoginScreen(),
    );
  }
}
```

### lib/features/auth/login_screen.dart
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'auth_provider.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Login')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 16),
            TextField(
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () {},
              child: const Text('Login'),
            ),
          ],
        ),
      ),
    );
  }
}
```

### lib/features/auth/auth_provider.dart
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});

class AuthState {
  final bool isLoggedIn;
  final String? email;

  AuthState({this.isLoggedIn = false, this.email});
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(AuthState());

  void login(String email, String password) {
    state = AuthState(isLoggedIn: true, email: email);
  }

  void logout() {
    state = AuthState();
  }
}
```
'''

    print("="*60)
    print("🔧 Testing Project Scaffolder")
    print("="*60)

    scaffolder = ProjectScaffolder()
    project_path = scaffolder.scaffold_from_text(
        sample_output,
        project_name="test_login_app",
        overwrite=True,
    )

    print(f"\n✅ Project created at: {project_path}")

    # Show generated pubspec
    pubspec_path = project_path / 'pubspec.yaml'
    if pubspec_path.exists():
        print("\n📄 Generated pubspec.yaml:")
        print("-"*40)
        with open(pubspec_path) as f:
            print(f.read())


if __name__ == "__main__":
    main()
