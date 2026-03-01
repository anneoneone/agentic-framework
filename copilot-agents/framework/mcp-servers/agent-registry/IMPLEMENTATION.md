# Agent Registry MCP Server - Implementation Summary

## Overview

A production-quality MCP (Model Context Protocol) server for programmatic agent discovery and routing in the copilot-agents framework. Replaces file-scanning protocols with structured registry queries via standardized MCP tools.

**Status**: ✓ Complete and ready for integration
**Language**: Python 3.10+
**Dependencies**: `mcp>=1.0.0` (no YAML library required)
**Location**: `/sessions/serene-happy-dijkstra/mnt/agentic-framework/copilot-agents/framework/mcp-servers/agent-registry/`

## Architecture

### Core Components

#### 1. Frontmatter Parser (`parse_frontmatter()`)
- **Purpose**: Extract YAML frontmatter from agent markdown files
- **Approach**: Regex-based parsing (no external dependencies)
- **Supported Formats**:
  - Key-value pairs: `name: value`
  - List items: `- item`
  - Inline arrays: `[item1, item2]`
  - Quoted strings: `"value"`
  - Nested structures: `scope.primary`
- **Lines**: ~40 lines of pure Python

#### 2. AgentRegistry Class
**Core discovery and metadata management**

```python
class AgentRegistry:
    def __init__(root_path: Path)          # Auto-detect copilot-agents/
    def find_agent_files() -> list[Path]   # Scan all .agent.md files
    def parse_agent(path: Path) -> AgentMetadata      # Extract metadata
    def list_agents(stack: str = None) -> list[AgentSummary]
    def get_agent(name: str) -> AgentMetadata
    def find_agents_for_task(task_description, stack) -> list[(AgentSummary, float)]
    def validate_agent(path: str) -> ValidationResult
    def get_capability_map(stack: str) -> dict[str, set[str]]
```

**Key Methods**:
- `find_agent_files()`: Glob-based search with symlink resolution
- `parse_agent()`: Metadata extraction + caching
- `find_agents_for_task()`: Keyword-based matching with scoring
- `validate_agent()`: Reuses validation logic from validate-agent.py
- `get_capability_map()`: Builds keyword → agent index

#### 3. AgentCache Class
**In-memory caching with TTL**

```python
class AgentCache:
    def __init__(ttl_hours: int = 24)
    def get_agent(name: str) -> Optional[AgentMetadata]
    def set_agent(name: str, metadata: AgentMetadata)
    def get_capability_map(stack: str) -> Optional[dict]
    def set_capability_map(stack: str, cap_map: dict)
    def clear()
```

**Performance**:
- First `list_agents()` call: ~100-500ms (full scan)
- Cached calls: ~1-5ms
- TTL: 24 hours
- Separate caches for agents and capability maps

#### 4. MCP Server Integration
**Async server using `mcp` SDK**

```python
server = Server("agent-registry")

@server.list_tools() -> list[Tool]        # Advertise tools
@server.call_tool(name, args) -> TextContent  # Handle tool calls
```

**Transport**: Stdio (suitable for VS Code integration)

### Data Models

```python
@dataclass
class AgentMetadata:
    name: str
    description: str
    version: str
    keywords: list[str]
    scope: dict[str, Any]
    stack: Optional[str]
    path: Optional[str]
    line_count: int

@dataclass
class AgentSummary:
    name: str
    description: str
    version: str
    keywords: list[str]
    stack: Optional[str]
    path: Optional[str]

@dataclass
class ValidationResult:
    path: str
    valid: bool
    errors: list[str]
    warnings: list[str]
    info: list[str]
```

## API - Available Tools

### 1. `list_agents`
**List all agents with optional stack filtering**

**Input**:
```json
{
  "stack": "live-moafunk"  // optional
}
```

**Output**:
```json
[
  {
    "name": "vue-frontend",
    "description": "Vue.js frontend development",
    "version": "1.0",
    "keywords": ["vue", "frontend", "javascript"],
    "stack": "live-moafunk",
    "path": "stacks/live-moafunk/.github/agents/vue-frontend.agent.md"
  }
]
```

**Implementation**:
- Scans all `.agent.md` files via `find_agent_files()`
- Parses metadata from frontmatter
- Caches results for 24h TTL
- Returns sorted by name

### 2. `get_agent`
**Retrieve full agent metadata**

**Input**:
```json
{
  "name": "documentation"
}
```

**Output**:
```json
{
  "name": "documentation",
  "description": "Documentation architecture and API documentation patterns",
  "version": "1.0",
  "keywords": ["documentation", "api-docs", "markdown", "plantUML", ...],
  "scope": {
    "primary": ["Architecture documentation", "API documentation generation"],
    "required": ["Reference actual documentation files"]
  },
  "stack": null,
  "path": "framework/core/shared-agents/documentation.agent.md",
  "line_count": 45
}
```

**Implementation**:
- Searches for agent by name
- Returns full metadata from cache or parses fresh
- Includes scope, keywords, and file metrics

### 3. `find_agents_for_task`
**Find agents matching a task description using keyword scoring**

**Input**:
```json
{
  "task_description": "I need to build a React component for authentication",
  "stack": "live-moafunk"  // optional
}
```

**Output**:
```json
[
  {
    "agent": {
      "name": "vue-frontend",
      "description": "Vue.js frontend development",
      "version": "1.0",
      "keywords": ["vue", "frontend", "javascript"],
      "stack": "live-moafunk",
      "path": "stacks/live-moafunk/.github/agents/vue-frontend.agent.md"
    },
    "score": 12,
    "match_quality": "excellent"
  },
  {
    "agent": {
      "name": "javascript-tooling",
      ...
    },
    "score": 5,
    "match_quality": "good"
  }
]
```

**Scoring Algorithm**:
- Extract task keywords (words > 4 chars)
- For each keyword:
  - Exact match in agent keywords: **+5 points**
  - Partial match (substring): **+2 points**
  - Category match (in description): **+1 point**
- Sort results by score descending
- Filter out zero-score agents

**Match Quality Tiers**:
- Excellent: score ≥ 10
- Good: score ≥ 5
- Fair: score ≥ 1

### 4. `validate_agent`
**Validate agent file structure**

**Input**:
```json
{
  "path": "framework/core/shared-agents/documentation.agent.md"
}
```

**Output**:
```json
{
  "path": "framework/core/shared-agents/documentation.agent.md",
  "valid": true,
  "errors": [],
  "warnings": [],
  "info": [
    "Consider adding section: patterns",
    "Consider adding section: failure modes"
  ]
}
```

**Validation Checks**:
1. **Frontmatter**: Presence and YAML validity
2. **Required fields**: `name`, `description`, `version`
3. **Recommended fields**: `keywords` (≥3), `scope`
4. **Section structure**: Role, scope, key files (with aliases)
5. **Naming consistency**: Frontmatter name matches filename
6. **Kebab-case**: name matches `[a-z][a-z0-9-]*`
7. **Line count**: 30-250 recommended (warn if outside range)
8. **Description length**: 10-200 chars recommended

### 5. `get_capability_map`
**Build keyword → agent name index for a stack**

**Input**:
```json
{
  "stack": "live-moafunk"
}
```

**Output**:
```json
{
  "vue": ["vue-frontend"],
  "frontend": ["vue-frontend"],
  "javascript": ["vue-frontend", "javascript-tooling"],
  "backend": ["axum-backend"],
  "rust": ["axum-backend"],
  "docker": ["docker-deploy"],
  "deployment": ["docker-deploy", "terraform-infra"]
}
```

**Use Cases**:
- Quick capability lookup ("what agents handle Rust?")
- Routing logic implementation
- UI/dashboard filtering
- Discovery indexing

## Implementation Details

### Path Resolution

**Auto-detection**:
```python
# server.py is at: copilot-agents/framework/mcp-servers/agent-registry/server.py
# Root is at:      copilot-agents/

server_dir = Path(__file__).parent.parent.parent.parent
root_path = server_dir  # copilot-agents/
```

### Agent File Discovery

**Patterns**:
1. Stack-specific: `stacks/{stack}/.github/agents/*.agent.md`
2. Framework core: `framework/core/**/*.agent.md`
3. All agents: `**/*.agent.md`

**Features**:
- Glob-based search (no recursive os.walk)
- Symlink resolution (deduplicate via `.resolve()`)
- Path normalization (relative to root)

### Frontmatter Parsing

**Example input**:
```yaml
---
name: documentation
description: Documentation architecture and API documentation patterns
version: 1.0
keywords:
  - documentation
  - api-docs
  - markdown
  - plantUML
scope:
  primary:
    - Architecture documentation
    - API documentation generation
  required:
    - Reference actual documentation files
---
```

**Parser implementation**:
- Split on `---` delimiters (regex: `r"^---$"`)
- Process each line:
  - List item: `if line.startswith("  - ")`
  - Key-value: `re.match(r"^(\w[\w-]*):\s*(.*)$")`
  - Inline array: `if value.startswith("[") and value.endswith("]")`
- Return `(dict, body)` tuple

**No external deps**: Uses only `re` and `pathlib`

### Caching Strategy

**Time-based TTL**:
```python
self.agents: dict[str, tuple[AgentMetadata, float]] = {}

def get_agent(name: str):
    if name in self.agents:
        metadata, timestamp = self.agents[name]
        if time.time() - timestamp < self.ttl_seconds:
            return metadata
        del self.agents[name]
    return None

def set_agent(name: str, metadata: AgentMetadata):
    self.agents[name] = (metadata, time.time())
```

**Cache characteristics**:
- Per-agent caching (fine-grained)
- Separate capability map cache
- 24-hour default TTL
- Manual clear via `cache.clear()`
- No file watching (refresh on timer)

### Error Handling

**Graceful degradation**:
```python
try:
    content = path.read_text(encoding="utf-8")
except (OSError, UnicodeDecodeError):
    return None  # Skip unreadable files

if frontmatter is None:
    return None  # Skip files without frontmatter

if "name" not in frontmatter:
    result.valid = False
    result.errors.append("Missing required field: name")
```

## Integration Points

### VS Code / Claude Desktop

**Configuration** (see `mcp-config-example.json`):
```json
{
  "mcpServers": {
    "agent-registry": {
      "command": "python",
      "args": ["-m", "agent_registry.server"],
      "description": "Agent discovery and routing"
    }
  }
}
```

### Python Direct Usage

```python
from agent_registry.server import AgentRegistry

registry = AgentRegistry()
agents = registry.list_agents(stack="live-moafunk")
print(agents)
```

### Docker

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -e .
ENTRYPOINT ["agent-registry"]
```

## File Structure

```
copilot-agents/framework/mcp-servers/agent-registry/
├── __init__.py                 # Package marker (empty)
├── server.py                   # Main MCP server (830 lines)
│   ├── Data models (AgentMetadata, AgentSummary, ValidationResult)
│   ├── Frontmatter parser (parse_frontmatter)
│   ├── AgentCache class
│   ├── AgentRegistry class (7 public methods)
│   ├── MCP server setup (list_tools, call_tool)
│   └── main() entry point
├── pyproject.toml              # Package metadata + entry points
├── README.md                   # User documentation
├── IMPLEMENTATION.md           # This file
├── example_usage.py            # Standalone example script
├── mcp-config-example.json     # Configuration examples
└── tests/
    ├── __init__.py
    ├── test_parser.py          # Frontmatter parser tests
    └── test_registry.py        # Registry functionality tests
```

## Key Design Decisions

### 1. No External YAML Library
**Rationale**: Keep dependencies minimal, match validate-agent.py approach
**Trade-off**: Supports common YAML patterns but not full spec
**Benefit**: ~40 lines of simple regex vs 10+ KB dependency

### 2. Keyword-Based Matching (Not ML)
**Rationale**: Deterministic, explainable, no model dependencies
**Scoring**: Simple point system (exact/partial/category)
**Alternative**: Could add embedding-based search later

### 3. In-Memory Caching
**Rationale**: Fast for typical use (< 500 agents)
**Scale**: For >1000 agents, consider SQLite persistence
**TTL**: 24 hours balances freshness vs performance

### 4. Glob-Based Discovery
**Rationale**: Fast, clean, works with symlinks
**Patterns**: Stack-specific + framework + all
**Deduplication**: Via `.resolve()` path normalization

### 5. Dataclasses for Models
**Rationale**: Clean, JSON-serializable, type hints
**Serialization**: `asdict()` for JSON output
**Compatibility**: Works with MCP TextContent

### 6. Stdio Transport
**Rationale**: Standard for VS Code extensions
**Communication**: JSON-RPC over stdin/stdout
**Benefit**: Works in any environment (local, remote, container)

## Performance Characteristics

### Benchmarks (Estimated)

| Operation | Time | Notes |
|-----------|------|-------|
| First `list_agents()` | 100-500ms | Full scan, ~50-500 files |
| Cached `list_agents()` | 1-5ms | In-memory lookup |
| `get_agent()` (uncached) | 50-100ms | Single file parse |
| `get_agent()` (cached) | <1ms | Dictionary lookup |
| `find_agents_for_task()` | 10-50ms | Keyword scoring |
| `validate_agent()` | 5-20ms | Validation checks |
| `get_capability_map()` | 50-100ms | Index build |

### Optimization Opportunities

1. **Database persistence**: SQLite for >1000 agents
2. **Real-time invalidation**: File watchers instead of TTL
3. **Async file I/O**: For very large repositories
4. **Partial parsing**: Cache frontmatter separately from body
5. **ML-based scoring**: Embedding search for semantic matching

## Testing

### Unit Tests

**File**: `tests/test_parser.py`
- Frontmatter parsing (valid, inline arrays, quoted values)
- Error handling (missing delimiters, incomplete)
- Edge cases (empty fields, special characters)

**File**: `tests/test_registry.py`
- Agent discovery (find_agent_files, all patterns)
- Metadata extraction (parse_agent, field validation)
- Task-based search (keyword scoring)
- Validation (checks, errors, warnings)
- Capability mapping

### Running Tests

```bash
cd /path/to/agent-registry
pip install -e ".[dev]"
pytest tests/ -v
pytest tests/test_registry.py::TestAgentRegistry::test_list_agents -v
pytest --cov=agent_registry tests/
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'mcp'"

```bash
pip install "mcp>=1.0.0"
```

### "Agent not found"

1. Check agent file exists and has `.agent.md` extension
2. Verify frontmatter has `name` field matching filename
3. Run `validate_agent()` to check for errors
4. Clear cache: restart server or call `registry.cache.clear()`

### "Server not appearing in VS Code"

1. Verify installation: `which agent-registry`
2. Check config: VS Code settings.json or mcp.json
3. Restart VS Code or reload extension
4. Check extension logs: `Help > Show Logs > Extension Host`

### "Empty results from `find_agents_for_task`"

1. Check task has words > 4 characters
2. Verify agents have `keywords` in frontmatter
3. Try longer task description with more details
4. Check if agents exist: run `list_agents` first

## Future Enhancements

### Phase 2: Persistence
- [ ] SQLite backend for agent metadata
- [ ] Incremental indexing
- [ ] Query API (filter by version, status, etc.)

### Phase 3: Intelligence
- [ ] ML-based semantic search (embeddings)
- [ ] Agent dependency graph
- [ ] Usage metrics and rating system
- [ ] Auto-categorization

### Phase 4: Integration
- [ ] GraphQL API
- [ ] Web dashboard
- [ ] Real-time collaboration
- [ ] Agent marketplace

## License

MIT

## Contact

Copilot Agents Framework Team
