# Knowledge Search MCP Server

A self-contained MCP server for semantic knowledge search across agent-framework stacks. Uses TF-IDF scoring with BM25 ranking for relevance—no external vector database required.

## Features

- **TF-IDF Indexing**: Fast, self-contained semantic search using TF-IDF with BM25 ranking
- **Multi-Format Support**: Indexes both JSONL and Markdown knowledge files
- **Stack-Aware**: Organized search across multiple stacks with stack filtering
- **Smart Caching**: 1-hour TTL index cache for performance
- **Context Resolution**: Load just-in-time context from multiple sources for plan execution
- **Decision Search**: Find decisions across stacks with plan filtering

## Installation

```bash
pip install -e .
```

## Usage

### Tools

#### `search_knowledge`
Search for knowledge across stacks.

```json
{
  "query": "authentication methods",
  "stack": "auth-service",
  "limit": 10
}
```

Returns ranked results with TF-IDF scores, file paths, and content previews.

#### `get_knowledge_entry`
Retrieve full content of a specific knowledge entry.

```json
{
  "file": "stacks/auth-service/docs/knowledge/api-docs.jsonl",
  "stack": "auth-service",
  "index": 0
}
```

#### `list_knowledge_files`
List all knowledge files in stacks.

```json
{
  "stack": "auth-service"
}
```

Returns file metadata: type, size, entry count.

#### `search_decisions`
Search for decisions across stacks.

```json
{
  "query": "database schema",
  "stack": "data-service",
  "plan_id": "plan-123"
}
```

#### `search_cross_stack`
Search across all stacks with results labeled by stack.

```json
{
  "query": "API authentication",
  "limit": 5
}
```

Returns results grouped by stack.

#### `resolve_context`
Resolve context from multiple sources for plan execution.

```json
{
  "context_sources": [
    {
      "type": "knowledge",
      "query": "database schema",
      "source": "data-service"
    },
    {
      "type": "file",
      "path": "stacks/data-service/docs/schema.md"
    },
    {
      "type": "plan_output",
      "plan_id": "plan-123",
      "step_id": "step-1"
    }
  ]
}
```

Supports context types:
- `knowledge`: Search knowledge files
- `file`: Read file contents
- `mcp_query`: Delegate to another MCP server
- `plan_output`: Reference plan step outputs

## Architecture

### Indexing Strategy

- **JSONL Files**: Each line is indexed as a separate document
- **Markdown Files**: Split by H2 headers (## ), each section is a document
- **Tokenization**: Lowercase, whitespace/punctuation split, stopword removal
- **Scoring**: BM25 ranking with k1=1.2, b=0.75

### File Structure

```
agent-framework/
├── stacks/
│   ├── auth-service/
│   │   └── docs/
│   │       └── knowledge/
│   │           ├── api.jsonl
│   │           └── guide.md
│   └── data-service/
│       └── docs/
│           └── knowledge/
│               └── schema.jsonl
├── framework/
│   └── mcp-servers/
│       └── knowledge-search/
│           ├── server.py
│           ├── pyproject.toml
│           └── README.md
```

### Caching

- Index built on first search, cached with 1-hour TTL
- Separate cache per stack + all-stacks searches
- Automatic expiry and rebuild when cache expires

## Performance

- First search per stack/query: ~100-500ms (indexing)
- Cached searches: <10ms
- Memory footprint: ~10MB per 1000 documents
- No external dependencies beyond mcp SDK

## Development

```bash
# Install in editable mode
pip install -e .

# Run server
python -m knowledge_search.server

# Test search
python -c "
from server import KnowledgeSearchServer
import asyncio

async def test():
    server = KnowledgeSearchServer()
    result = await server._search_knowledge('test query', limit=5)
    print(result.text)

asyncio.run(test())
"
```

## Integration

The Knowledge Search server is designed to be called by plan executors and other MCP clients. The `resolve_context` tool is especially useful for loading just-in-time context during plan execution.

## License

MIT
