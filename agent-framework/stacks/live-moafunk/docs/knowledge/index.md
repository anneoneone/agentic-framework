# Knowledge Index — live-moafunk

**Stats**: 13 files, 635 JSONL entries, 17 markdown sections, 150,361 bytes total

## Structured Data (JSONL)

| File | Entries | Size |
|------|---------|------|
| `api-endpoints.jsonl` | 16 | 1,416 B |
| `decisions/extracted-decisions.jsonl` | 323 | 73,603 B |
| `deployment-urls.jsonl` | 4 | 347 B |
| `env-vars.jsonl` | 17 | 2,261 B |

## Domain Knowledge (Markdown)

| File | Sections |
|------|----------|
| `code-style.md` | 2 |
| `db-schema.md` | 1 |
| `git-workflow.md` | 0 |
| `soundcloud-integration.md` | 5 |
| `telegram-bot-integration.md` | 5 |

## Extracted Knowledge (Auto-Generated)

Automatically extracted from completed plan steps by `extract-knowledge.py`.

| File | Entries | Size |
|------|---------|------|
| `extracted-blocker-resolutions.jsonl` | 2 | 526 B |
| `extracted-learnings.jsonl` | 140 | 31,700 B |
| `extracted-notes.jsonl` | 133 | 36,215 B |
| `decisions/extracted-decisions.jsonl` | 323 | 73,603 B |

## Querying Knowledge

Use the `knowledge-search` MCP server for semantic search:
```
knowledge-search.search_knowledge(query="...", stack="live-moafunk")
knowledge-search.search_decisions(query="...", stack="live-moafunk")
knowledge-search.search_cross_stack(query="...")
```
