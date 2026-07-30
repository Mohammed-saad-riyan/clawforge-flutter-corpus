# Quality Rubric

Score each source from 1 to 5.

## 5 — Excellent
- Production-ready Flutter code.
- Clear architecture and separation of concerns.
- Uses Riverpod, GoRouter, tests, and modern packages cleanly.
- Includes real issue fixes, PRs, or branch history.
- High relevance to app generation tasks.

## 4 — Strong
- Good structure and reusable patterns.
- Mostly production-grade, with some rough edges.
- Useful for retrieval and examples.

## 3 — Mixed
- Contains useful patterns, but also noise.
- Good for reference, not for direct imitation.

## 2 — Weak
- Mostly tutorial, boilerplate, or outdated code.
- Limited value for generation.

## 1 — Ignore
- Broken, trivial, obsolete, or off-target.
- Not useful for ClawForge.

## Promotion rules

Promote a source into `curated/` only when:
- It scores 4 or 5.
- It maps to a clearly useful Flutter pattern.
- It can be chunked into reusable units.
- It compiles or has clear fix history.
