# Agent Registry MCP Server

A Model Context Protocol (MCP) server for programmatic agent discovery and routing in the agent-framework framework.

Replaces file-scanning protocols with structured registry queries via MCP tools. Provides:
- **Agent discovery** by name, keywords, or task description
- **Metadata retrieval** with full frontmatter and section info
- **Capability indexing** for quick lookups
- **Validation** of agent file structure
- **Caching** with 24-hour TTL for performance

## Installation

```bash
pip install -e /path/to/agent-framework/framework/mcp-servers/agent-registry
```

Or add to your `requirements.txt`:
```
agent-registry-mcp @ file:///path/to/agent-framework/framework/mcp-servers/agent-registry
```

## Usage

### VS Code Integration (settings.json)

Add to your `.vscode/settings.json`:

```json
{
  "modelContextProtocol": {
    "servers": {
      "agent-registry": {
        "command": "agent-registry",
        "description": "Agent discovery and routing for agent-framework"
      }
    }
  }
}
```

Or in `.vscode/claude.json`:

```json
{
  "mcpServers": {
    "agent-registry": {
      "command": "agent-registry"
    }
  }
}
```

### Direct Execution

```bash
python -m agent_registry.server
```

The server will start listening on stdin/stdout for MCP messages.

## Available Tools

### `list_agents`

List all agents with optional stack filtering.

**Input:**
```json
{
  "stack": "live-moafunk"  // optional
}
```

**Output:**
```json
[
  {
    "name": "vue-frontend",
    "description": "Vue.js frontend development",
    "version": "1.0",
    "keywords": ["vue", "frontend", "javascript"],
    "stack": "live-moafunk",
    "path": "stacks/live-moafunk/agents/vue-frontend.agent.md"
  }
]
```

### `get_agent`

Retrieve full agent metadata.

**Input:**
```json
{
  "name": "documentation"
}
```

**Output:**
```json
{
  "name": "documentation",
  "description": "Documentation architecture and API documentation patterns",
  "version": "1.0",
  "keywords": ["documentation", "api-docs", "markdown"],
  "scope": {
    "primary": ["Architecture documentation", "API documentation generation"],
    "required": ["Reference actual documentation files"]
  },
  "stack": null,
  "path": "framework/core/shared-agents/documentation.agent.md",
  "line_count": 45
}
```

### `find_agents_for_task`

Find agents matching a task description using keyword scoring.

**Input:**
```json
{
  "task_description": "I need to build a React component for user authentication",
  "stack": "live-moafunk"  // optional
}
```

**Output:**
```json
[
  {
    "agent": {
      "name": "vue-frontend",
      "description": "Vue.js frontend development",
      "version": "1.0",
      "keywords": ["vue", "frontend", "javascript"],
      "stack": "live-moafunk",
      "path": "stacks/live-moafunk/agents/vue-frontend.agent.md"
    },
    "score": 12,
    "match_quality": "excellent"
  }
]
```

**Scoring:**
- Exact keyword match: +5 points
- Partial match (substring): +2 points
- Category match (appears in description): +1 point

### `validate_agent`

Validate an agent file for correctness.

**Input:**
```json
{
  "path": "framework/core/shared-agents/documentation.agent.md"
}
```

**Output:**
```json
{
  "path": "framework/core/shared-agents/documentation.agent.md",
  "valid": true,
  "errors": [],
  "warnings": [],
  "info": []
}
```

**Checks:**
1. YAML frontmatter presence and validity
2. Required fields: `name`, `description`, `version`
3. Recommended fields: `keywords`, `scope`
4. Section structure (role, scope, key files)
5. File naming consistency
6. Line count range (30-250 recommended)

### `get_capability_map`

Build a keyword → agent name index for a stack.

**Input:**
```json
{
  "stack": "live-moafunk"
}
```

**Output:**
```json
{
  "vue": ["vue-frontend"],
  "frontend": ["vue-frontend"],
  "javascript": ["vue-frontend"],
  "backend": ["axum-backend"],
  "rust": ["axum-backend"],
  "docker": ["docker-deploy"],
  "deployment": ["docker-deploy"]
}
```

## Performance

The server implements in-memory caching with a 24-hour TTL:

- **First call** to `list_agents` scans all `.agent.md` files (~100-500ms depending on repo size)
- **Subsequent calls** use cached results (~1ms)
- **Cache expires** after 24 hours; new scan occurs on next request
- **Symlinks** are resolved to avoid duplicate processing

For large repositories or frequent use, consider caching at a higher level (e.g., in Claude/VS Code).

## Architecture

### Core Components

1. **FrontmatterParser** (`parse_frontmatter()`)
   - Regex-based YAML parsing (no external deps)
   - Supports key-value pairs, lists, and inline arrays
   - ~50 lines of simple Python

2. **AgentRegistry** (`AgentRegistry` class)
   - Core discovery and metadata logic
   - 5 public methods: `list_agents`, `get_agent`, `find_agents_for_task`, `validate_agent`, `get_capability_map`
   - Handles symlink resolution and stack filtering

3. **AgentCache** (`AgentCache` class)
   - In-memory cache with timestamp-based TTL
   - Separate caches for agents and capability maps
   - Can be cleared programmatically

4. **MCP Server** (`server` object)
   - Async server using `mcp` SDK
   - Tool implementations delegate to `AgentRegistry`
   - Stdio transport (suitable for VS Code integration)

### Key Design Decisions

- **No YAML library**: Uses regex-based parsing like `validate-agent.py`
- **Simple scoring**: Keyword-based matching (not ML-based)
- **Path resolution**: Auto-detects `copilot-agents/` root from server location
- **Symlink handling**: Resolves symlinks to avoid duplicates
- **JSON output**: All tool responses are JSON-serializable for MCP compatibility

## Development

### Running Tests

```bash
pytest tests/
```

### Linting and Formatting

```bash
black agent_registry/
ruff check agent_registry/
mypy agent_registry/
```

### Building

```bash
pip install build
python -m build
```

## File Structure

```
agent-framework/framework/mcp-servers/agent-registry/
├── __init__.py                 # Package marker
├── server.py                   # Main MCP server (800+ lines)
├── pyproject.toml              # Package metadata
├── README.md                   # This file
└── tests/                      # Test suite (optional)
    ├── test_parser.py
    ├── test_registry.py
    └── test_server.py
```

## Troubleshooting

**Server fails to start:**
- Check that `mcp>=1.0.0` is installed: `pip install mcp`
- Ensure Python 3.10+ is available: `python --version`

**Tools not appearing in Claude:**
- Verify server is running: `ps aux | grep agent-registry`
- Check VS Code settings: `settings.json` or `mcp.json` properly formatted
- Restart Claude or VS Code

**Empty results from `find_agents_for_task`:**
- Keywords must be > 4 characters
- Check that agent files have `keywords` in frontmatter
- Try `list_agents` to verify agents are discoverable

**Slow response on first call:**
- Normal behavior: first call scans all agents
- Subsequent calls are cached (1-5ms)
- Cache refreshes every 24 hours

## Future Enhancements

- [ ] Database persistence (SQLite) for larger deployments
- [ ] ML-based semantic similarity (embedding-based matching)
- [ ] Agent rating/usage metrics
- [ ] Real-time file watching for cache invalidation
- [ ] GraphQL API for complex queries
- [ ] Agent dependency graph visualization

## License

MIT
