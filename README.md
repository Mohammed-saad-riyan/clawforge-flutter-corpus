# ClawForge

**A self-hosted Flutter code generation system powered by semantic retrieval and Qwen 2.5 Coder.**

ClawForge generates production-quality Flutter applications from natural language prompts, using a curated corpus of 5,754 real-world code snippets and semantic search to provide relevant context to a self-hosted 7B parameter model.

---

## What Makes This Different

| Traditional AI Coding | ClawForge |
|----------------------|-----------|
| Relies on external APIs (OpenAI, Anthropic) | **Self-hosted** on Modal - full control, no API costs |
| Generic code generation | **Flutter-specialized** with domain-specific templates |
| No code context | **5,754 real code snippets** from production apps |
| Keyword/random retrieval | **Semantic search** finds conceptually similar code |
| Single file output | **Multi-file scaffolding** creates complete projects |
| Black box | **Fully transparent** pipeline you can inspect and modify |

---

## How It Works

```
"Build a food delivery app with cart"
              │
              ▼
     ┌────────────────┐
     │ Template Match │  → FOOD_DELIVERY template
     └────────────────┘
              │
              ▼
     ┌────────────────┐
     │ Semantic Search│  → Find similar code in corpus
     └────────────────┘    (CartProvider, OrderService, etc.)
              │
              ▼
     ┌────────────────┐
     │ Context Build  │  → Template + 8 code examples
     └────────────────┘
              │
              ▼
     ┌────────────────┐
     │ Qwen 2.5 Coder │  → Generate with real examples
     └────────────────┘
              │
              ▼
     ┌────────────────┐
     │ Project Scaffold│ → Complete Flutter project
     └────────────────┘

Output:
  my_app/
  ├── lib/
  │   ├── main.dart
  │   └── features/
  │       ├── cart/
  │       └── restaurant/
  ├── pubspec.yaml
  └── analysis_options.yaml
```

---

## The Knowledge Base

We built a specialized Flutter knowledge base from scratch:

| What | Count |
|------|-------|
| Source repositories | 109 |
| Dart files indexed | 24,617 |
| Classes extracted | 40,147 |
| Widgets indexed | 17,068 |
| **Code snippets** | **5,754** |
| App templates | 20 |
| Packages tracked | 1,098 |

### Snippet Types
- **Widgets** (4,319) - Complete UI implementations
- **Services** (970) - API clients, repositories
- **Providers** (158) - State management (Riverpod, Bloc)
- **Models** (307) - Data classes, entities

### Detected Patterns
`auth` `forms` `navigation` `networking` `riverpod` `bloc` `local_storage` `lists` `async_ui` `animations`

---

## Semantic Search

The key innovation is **semantic code retrieval**. Instead of keyword matching, we use embeddings to find conceptually similar code.

**Query:** `"shopping cart with add remove items"`

| Rank | Snippet | Score | Why It Matched |
|------|---------|-------|----------------|
| 1 | CartProvider | 0.371 | Cart state management |
| 2 | CartViewModel | 0.359 | Cart business logic |
| 3 | GetItemsInCartUseCase | 0.329 | Cart operations |
| 4 | AddToCartMenu | 0.313 | Add to cart UI |

The model receives **actual working code** as reference, not just descriptions.

---

## Quick Start

```bash
# Clone
git clone https://github.com/Mohammed-saad-riyan/clawforge-flutter-corpus.git
cd clawforge-flutter-corpus

# Setup
python -m venv .venv
source .venv/bin/activate
pip install pyyaml httpx sentence-transformers numpy tqdm

# Generate a Flutter project
cd scripts
python generate.py "Build a todo app with add and delete" --scaffold

# Output
# generated/todo_app/
# ├── lib/main.dart
# ├── lib/features/todo/...
# ├── pubspec.yaml
# └── analysis_options.yaml
```

---

## What We Built

### Core Pipeline (`scripts/`)

| Script | Purpose |
|--------|---------|
| `generate.py` | Main generation pipeline |
| `modal_client.py` | Qwen 2.5 Coder API client |
| `match_template.py` | Rule-based template matching |
| `knowledge_retriever.py` | Metadata retrieval |
| `semantic_retriever.py` | Embedding-based code search |
| `scaffold_project.py` | Multi-file project creation |

### Ingestion Pipeline

| Script | Purpose |
|--------|---------|
| `clone_sources.py` | Clone repos with auto branch detection |
| `dart_ast_extractor.py` | Extract classes, widgets, imports |
| `extract_snippets.py` | Extract full code implementations |
| `embed_snippets.py` | Generate semantic embeddings |
| `discover_repos.py` | Find new repos via GitHub API |

### Knowledge Base (`curated/`)

```
curated/
├── extracted/           # AST metadata per repo
├── snippets/
│   ├── all_snippets.jsonl      # 5,754 code snippets
│   ├── widget_snippets.jsonl
│   ├── service_snippets.jsonl
│   └── ...
└── embeddings/
    ├── snippet_embeddings.npy  # 384-dim vectors (8.4 MB)
    └── embedding_metadata.json
```

### Templates (`templates/`)

20 app type templates:
- ECOMMERCE, FOOD_DELIVERY, SOCIAL_MEDIA
- TASK_TODO, FITNESS, FINANCE, CHAT
- NEWS, MUSIC, VIDEO, WEATHER
- HEALTHCARE, EDUCATION, REAL_ESTATE
- JOB_PORTAL, EVENT, TRAVEL
- BASIC_CRUD, DASHBOARD, PORTFOLIO

---

## Generated Code Quality

ClawForge generates Flutter code with:

- **Riverpod** state management
- **GoRouter** navigation
- **Freezed** immutable models
- **Clean Architecture** structure
- Proper error/loading states
- Type-safe code

```dart
// Example: Generated main.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

void main() {
  runApp(ProviderScope(child: MyApp()));
}

class MyApp extends StatelessWidget {
  final _router = GoRouter(routes: [
    GoRoute(path: '/', builder: (_, __) => HomeScreen()),
  ]);

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(routerConfig: _router);
  }
}
```

---

## Requirements

- Python 3.11+
- Modal account with Qwen 2.5 Coder deployed
- ~10GB disk space for corpus
- GitHub token (optional, for repo discovery)

---

## Architecture Deep Dive

See [CLAWFORGE.md](CLAWFORGE.md) for complete technical documentation including:
- Detailed architecture diagrams
- Component API documentation
- Embedding system explanation
- Setup from scratch guide
- Comparison with frontier models

---

## Roadmap

- [x] Repository ingestion pipeline
- [x] Dart AST extraction
- [x] Code snippet extraction
- [x] Semantic embeddings
- [x] Template matching
- [x] Multi-file scaffolding
- [ ] Validation loop (`dart analyze` + auto-fix)
- [ ] Fallback repo discovery
- [ ] Error repair dataset
- [ ] REST API wrapper
- [ ] VS Code extension

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note on corpus data:** The code snippets in `curated/` are extracted from open-source Flutter repositories. Each source repository retains its original license. See `sources/sources.csv` for the full list of source repositories.

---

## Acknowledgments

- [Qwen 2.5 Coder](https://github.com/QwenLM/Qwen2.5-Coder) - The 7B model powering generation
- [Modal](https://modal.com) - Serverless GPU hosting
- [Sentence Transformers](https://www.sbert.net/) - Embedding model
- Flutter open-source community - The corpus source material
