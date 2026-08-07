# ClawForge - Flutter Code Generation System

> A self-hosted AI system for generating production-quality Flutter applications using Qwen 2.5 Coder on Modal, powered by semantic code retrieval from a curated Flutter corpus.

## Overview

ClawForge is an alternative to cloud-based AI coding assistants, specifically optimized for Flutter development. Instead of relying on external APIs, it uses:

- **Qwen 2.5 Coder 7B** - Self-hosted on Modal (vLLM with tensor parallelism)
- **Semantic Code Retrieval** - 5,754 production code snippets with embeddings
- **Template-based Generation** - 20 app type templates for structured output
- **Multi-file Scaffolding** - Generates complete Flutter projects

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER PROMPT                               │
│              "Build a food delivery app with cart"               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    1. TEMPLATE MATCHING                          │
│                                                                  │
│   Rule-based matcher scores prompt against 20 templates         │
│   Output: FOOD_DELIVERY template (score: 30)                    │
│                                                                  │
│   Templates: ECOMMERCE, SOCIAL_MEDIA, FOOD_DELIVERY,            │
│              TASK_TODO, FITNESS, FINANCE, CHAT, etc.            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  2. KNOWLEDGE RETRIEVAL                          │
│                                                                  │
│   Retrieves metadata for the template:                          │
│   - Widget examples (34 widgets)                                │
│   - Architectural patterns                                       │
│   - Recommended packages (dio, riverpod, go_router, etc.)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 3. SEMANTIC CODE SEARCH                          │
│                                                                  │
│   Query: "food delivery app with cart"                          │
│           ↓                                                      │
│   Encode with all-MiniLM-L6-v2 → 384-dim vector                 │
│           ↓                                                      │
│   Cosine similarity with 5,754 snippet embeddings               │
│           ↓                                                      │
│   Top 8 matches with FULL implementation code:                  │
│   - CartProvider [score: 0.371]                                 │
│   - OrderServices [score: 0.329]                                │
│   - LatestOrders widget [score: 0.298]                          │
│   - ...                                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   4. CONTEXT ASSEMBLY                            │
│                                                                  │
│   Combined context (~12KB):                                      │
│   - Template YAML (screens, patterns, packages)                 │
│   - Widget metadata                                              │
│   - Full code snippets (actual implementations)                 │
│   - System prompt with output format rules                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                5. MODAL / QWEN 2.5 CODER                         │
│                                                                  │
│   POST https://[user]--clawforge-llm-generate.modal.run         │
│                                                                  │
│   Model: Qwen 2.5 Coder 7B                                      │
│   Temperature: 0.2                                               │
│   Max tokens: 4096-8192                                         │
│                                                                  │
│   Output: Markdown with file markers                            │
│   ### lib/main.dart                                             │
│   ```dart                                                        │
│   // generated code                                              │
│   ```                                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  6. PROJECT SCAFFOLDING                          │
│                                                                  │
│   Parser extracts files from markdown output                    │
│   Creates directory structure:                                   │
│                                                                  │
│   generated/food_delivery_app/                                  │
│   ├── lib/                                                       │
│   │   ├── main.dart                                             │
│   │   └── features/                                              │
│   │       ├── cart/                                              │
│   │       │   ├── cart_screen.dart                              │
│   │       │   └── cart_provider.dart                            │
│   │       └── restaurant/                                        │
│   │           └── restaurant_list.dart                          │
│   ├── pubspec.yaml  (auto-generated with dependencies)         │
│   └── analysis_options.yaml                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Corpus Statistics

| Metric | Value |
|--------|-------|
| Source Repositories | 109 |
| Dart Files Indexed | 24,617 |
| Classes Extracted | 40,147 |
| Widgets Indexed | 17,068 |
| Code Snippets | 5,754 |
| Snippet Types | widget, service, provider, model |
| Embedding Dimensions | 384 |
| Embedding Model | all-MiniLM-L6-v2 |
| Embedding Size | 8.4 MB |
| App Templates | 20 |
| Packages Indexed | 1,098 |

## Directory Structure

```
clawforge-flutter-corpus/
├── scripts/                    # Core pipeline scripts
│   ├── generate.py             # Main generation pipeline
│   ├── modal_client.py         # Modal API client
│   ├── match_template.py       # Template matching
│   ├── knowledge_retriever.py  # Metadata retrieval
│   ├── semantic_retriever.py   # Embedding-based code search
│   ├── scaffold_project.py     # Multi-file project creation
│   ├── embed_snippets.py       # Embedding generation
│   ├── extract_snippets.py     # Code snippet extraction
│   ├── extract_all.py          # Bulk metadata extraction
│   ├── dart_ast_extractor.py   # Dart AST parsing
│   ├── clone_sources.py        # Repository cloning
│   ├── discover_repos.py       # GitHub repo discovery
│   └── merge_sources.py        # Source deduplication
│
├── templates/                   # App type templates
│   ├── template_registry.yaml  # Template definitions
│   └── *.yaml                   # Individual templates
│
├── curated/                     # Processed knowledge base
│   ├── extracted/               # AST extraction results
│   │   └── [repo_id]/           # Per-repo metadata
│   ├── snippets/                # Code snippets
│   │   ├── all_snippets.jsonl   # All snippets
│   │   ├── widget_snippets.jsonl
│   │   ├── service_snippets.jsonl
│   │   ├── provider_snippets.jsonl
│   │   └── model_snippets.jsonl
│   └── embeddings/              # Semantic embeddings
│       ├── snippet_embeddings.npy
│       └── embedding_metadata.json
│
├── sources/                     # Cloned repositories
│   ├── sources.csv              # Repository manifest
│   └── [repo_id]/               # Cloned repo content
│
├── generated/                   # Output projects
│   └── [project_name]/          # Generated Flutter project
│
└── output/                      # Raw generation output
    └── [timestamp]_*.dart       # Saved generations
```

## Components

### 1. Template Matcher (`match_template.py`)

Rule-based system that matches user prompts to app type templates.

```python
from match_template import match_template

match = match_template("Build a food delivery app")
# Returns: TemplateMatch(name="FOOD_DELIVERY", score=30)
```

**Templates Available:**
- ECOMMERCE, SOCIAL_MEDIA, FOOD_DELIVERY
- TASK_TODO, FITNESS, FINANCE, TRAVEL
- CHAT, NEWS, MUSIC, VIDEO
- WEATHER, HEALTHCARE, EDUCATION
- REAL_ESTATE, JOB_PORTAL, EVENT
- BASIC_CRUD, DASHBOARD, PORTFOLIO

### 2. Knowledge Retriever (`knowledge_retriever.py`)

Retrieves metadata from the extracted corpus based on template.

```python
from knowledge_retriever import KnowledgeRetriever

retriever = KnowledgeRetriever()
result = retriever.retrieve_for_template(template, user_prompt)
# Returns: widgets, patterns, packages
```

### 3. Semantic Retriever (`semantic_retriever.py`)

Embedding-based code search using cosine similarity.

```python
from semantic_retriever import SemanticRetriever

retriever = SemanticRetriever()
matches = retriever.search("login screen with email validation", top_k=10)
# Returns actual code implementations with similarity scores
```

**How it works:**
1. Query is encoded to 384-dim vector using `all-MiniLM-L6-v2`
2. Cosine similarity computed against 5,754 pre-computed snippet embeddings
3. Top-K results returned with full implementation code

### 4. Modal Client (`modal_client.py`)

HTTP client for the self-hosted Qwen 2.5 Coder model.

```python
from modal_client import ModalClient

client = ModalClient()
response = client.generate_flutter(
    user_prompt="Build a todo app",
    template_context=template_yaml,
    knowledge_context=context_string,
    max_tokens=4096,
)
```

**Endpoint:** `https://[user]--clawforge-llm-generate.modal.run`

### 5. Project Scaffolder (`scaffold_project.py`)

Parses model output and creates complete Flutter projects.

```python
from scaffold_project import ProjectScaffolder

scaffolder = ProjectScaffolder()
project_path = scaffolder.scaffold_from_text(
    model_output,
    project_name="my_app",
)
```

**Features:**
- Extracts files from `### path/to/file.dart` markers
- Creates proper directory structure
- Auto-detects dependencies from imports
- Generates `pubspec.yaml` with correct packages

## Usage

### CLI Generation

```bash
# Activate environment
source .venv/bin/activate
cd scripts

# Generate with scaffolding (creates complete project)
python generate.py "Build a login app with email auth" --scaffold

# Generate with custom project name
python generate.py "Build a todo app" --scaffold --project-name my_todo

# Dry run (show context without calling Modal)
python generate.py "Build an ecommerce app" --dry-run

# Interactive mode
python generate.py --interactive

# Save raw output only
python generate.py "Build a chat app" --save
```

### Output

```
📚 Loaded 5754 embeddings (384-dim)

============================================================
🚀 ClawForge Generator
============================================================

📝 Prompt: Build a todo app

1️⃣  Matching template...
   ✅ Matched: TASK_TODO (score: 10)

2️⃣  Retrieving knowledge...
   ✅ Widgets: 32
   ✅ Patterns: 0
   ✅ Packages: 8

3️⃣  Semantic code search...
   ✅ Snippets: 8
      - TodoBloc (widget) [score: 0.461]
      - EditTodoScreenState (widget) [score: 0.437]
      ...

4️⃣  Assembling context...
   ✅ Total context: 7513 chars

5️⃣  Generating code...
   ✅ Generated: 1116 tokens

📁 Project created: generated/todo_app
   Files: 6
   - lib/main.dart
   - lib/features/todo/todo_screen.dart
   - lib/features/todo/todo_provider.dart
   - lib/features/todo/todo_model.dart
   - pubspec.yaml
   - analysis_options.yaml

🚀 Run: cd generated/todo_app && flutter pub get && flutter run
```

## Setup

### Prerequisites

- Python 3.11+
- Modal account with Qwen 2.5 Coder deployed
- GitHub token (for repo discovery)

### Installation

```bash
# Clone repository
git clone https://github.com/[user]/clawforge-flutter-corpus.git
cd clawforge-flutter-corpus

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install pyyaml httpx sentence-transformers numpy tqdm

# Set environment variables
export GITHUB_TOKEN="your_token"
export MODAL_CLAWFORGE_URL="https://[user]--clawforge-llm-generate.modal.run"
```

### Building the Corpus (if starting fresh)

```bash
# 1. Clone source repositories
python scripts/clone_sources.py

# 2. Extract metadata from Dart files
python scripts/extract_all.py

# 3. Extract code snippets
python scripts/extract_snippets.py

# 4. Generate embeddings
python scripts/embed_snippets.py
```

## Semantic Search Explained

Traditional keyword search finds files with matching words. Semantic search finds conceptually similar code.

**Example:**

Query: `"login screen with email validation"`

| Approach | Results |
|----------|---------|
| **Keyword** | Any file with "login", "email", or "validation" in name |
| **Semantic** | LoginForm, LoginScreen, AuthScreen - actual login implementations |

**How embeddings work:**

```
Code Snippet
     ↓
"widget: LoginForm
 patterns: auth, forms
 code: class LoginForm extends StatelessWidget { ... }"
     ↓
Embedding Model (all-MiniLM-L6-v2)
     ↓
384-dimensional vector [0.12, -0.34, 0.56, ...]
```

Similar concepts have similar vectors. Cosine similarity finds the closest matches.

## Generated Code Quality

The system generates Flutter code with:

- **Riverpod** state management
- **GoRouter** navigation
- **Freezed** immutable models
- **Clean Architecture** (features/domain/data/presentation)
- Proper error handling
- Loading/empty states
- Type-safe code

### Sample Output Structure

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

void main() {
  runApp(
    ProviderScope(
      child: MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  final GoRouter _router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, __) => HomeScreen()),
      GoRoute(path: '/detail/:id', builder: (_, state) => DetailScreen(id: state.params['id']!)),
    ],
  );

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(routerConfig: _router);
  }
}
```

## Comparison to Frontier Models

| Capability | ClawForge (7B + RAG) | Frontier (Claude/GPT-4) |
|------------|----------------------|-------------------------|
| Flutter syntax | ✅ Good | ✅ Excellent |
| Architecture patterns | ✅ Good (from examples) | ✅ Excellent |
| Novel problem solving | ⚠️ Limited | ✅ Strong |
| Multi-file output | ✅ Yes | ✅ Yes |
| Context window | 32K | 128K-200K |
| Cost per generation | ~$0 | $0.01-0.10 |
| Self-hosted | ✅ Yes | ❌ No |
| Offline capable | ✅ Yes | ❌ No |

**Best for:** Structured, template-based Flutter apps where patterns are known.

## Future Improvements

### Planned

1. **Validation Loop** - Run `dart analyze`, auto-fix errors
2. **Fallback Pipeline** - Auto-discover repos when no good matches
3. **Repair Dataset** - Learn from error patterns

### Potential

- Fine-tuning dataset generation
- REST API wrapper
- VS Code extension
- Iterative refinement ("add logout button to this")
- Multi-turn conversation context

## License

MIT

## Credits

Built with:
- [Qwen 2.5 Coder](https://github.com/QwenLM/Qwen2.5-Coder) - Code generation model
- [Modal](https://modal.com) - Model hosting
- [Sentence Transformers](https://www.sbert.net/) - Embeddings
- Flutter open-source community - Training corpus
