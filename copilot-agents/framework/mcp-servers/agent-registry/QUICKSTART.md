# Agent Registry MCP Server - Quick Start

## 60-Second Setup

### 1. Install

```bash
cd /sessions/serene-happy-dijkstra/mnt/agentic-framework/copilot-agents/framework/mcp-servers/agent-registry
pip install -e .
```

### 2. Verify

```bash
python -c "from agent_registry.server import AgentRegistry; print(AgentRegistry())"
```

Expected output: `<agent_registry.server.AgentRegistry object at 0x...>`

### 3. Run Standalone (No MCP)

```bash
python example_usage.py
```

Output shows:
- List of all agents
- Sample agent details
- Task-based matching
- Validation results

### 4. Run as MCP Server

```bash
python -m agent_registry.server
```

Server listens on stdin for MCP messages (used by VS Code, Claude Desktop)

## Integration with VS Code

**Edit** `.vscode/settings.json`:

```json
{
  "modelContextProtocol": {
    "servers": {
      "agent-registry": {
        "command": "python",
        "args": ["-m", "agent_registry.server"],
        "description": "Agent discovery"
      }
    }
  }
}
```

**Restart** VS Code. Agent registry tools appear in Claude.

## Integration with Claude Desktop

**Edit** `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-registry": {
      "command": "python",
      "args": ["-m", "agent_registry.server"]
    }
  }
}
```

**Restart** Claude Desktop.

## Using from Python

```python
from agent_registry.server import AgentRegistry

# Create registry
registry = AgentRegistry()

# List all agents
agents = registry.list_agents()
print(f"Found {len(agents)} agents")

# Get details
agent = registry.get_agent("documentation")
print(agent.description)

# Find agents for a task
task = "I need to write API documentation"
results = registry.find_agents_for_task(task)
for agent, score in results:
    print(f"{agent.name}: {score} points")

# Validate an agent
result = registry.validate_agent("path/to/agent.agent.md")
if result.valid:
    print("✓ Valid")
else:
    print("✗ Errors:", result.errors)

# Get capability map
cap_map = registry.get_capability_map("live-moafunk")
print(cap_map["frontend"])  # Agents handling frontend
```

## MCP Tool Reference

### list_agents
```
Input:  {"stack": "optional-stack-name"}
Output: Array of {name, description, version, keywords, stack, path}
```

### get_agent
```
Input:  {"name": "agent-name"}
Output: {name, description, version, keywords, scope, stack, path, line_count}
```

### find_agents_for_task
```
Input:  {"task_description": "...", "stack": "optional"}
Output: Array of {agent, score, match_quality}
```

### validate_agent
```
Input:  {"path": "path/to/agent.agent.md"}
Output: {path, valid, errors, warnings, info}
```

### get_capability_map
```
Input:  {"stack": "stack-name"}
Output: {keyword: [agent_names], ...}
```

## File Structure

```
agent-registry/
├── __init__.py           (empty)
├── server.py             (main implementation - 830 lines)
├── pyproject.toml        (package config)
├── README.md             (full documentation)
├── IMPLEMENTATION.md     (architecture details)
├── QUICKSTART.md         (this file)
├── example_usage.py      (standalone demo)
├── mcp-config-example.json
└── tests/
    ├── test_parser.py
    └── test_registry.py
```

## Common Tasks

### Find agents by stack

```python
agents = registry.list_agents(stack="live-moafunk")
```

### Find agents for a task

```python
task = "build a REST API with Rust"
matches = registry.find_agents_for_task(task)
# Returns sorted by keyword match score
```

### Check agent health

```python
result = registry.validate_agent("stacks/live-moafunk/.github/agents/axum-backend.agent.md")
print("Valid" if result.valid else "Invalid")
for error in result.errors:
    print(f"Error: {error}")
```

### Get all capabilities for a stack

```python
caps = registry.get_capability_map("gartenroboter3000")
for keyword, agents in sorted(caps.items()):
    print(f"{keyword}: {agents}")
```

## Performance Tips

**First call is slow (~200ms)** - this is normal, it scans all agent files.
**Subsequent calls are fast (~5ms)** - results are cached for 24 hours.

To restart with fresh data:

```python
registry.cache.clear()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No module named 'mcp'" | `pip install mcp>=1.0.0` |
| "Agent not found" | Check filename matches `name:` in frontmatter |
| Empty results | Task description needs words >4 chars |
| Slow first call | Normal - scans all .agent.md files |

## Next Steps

1. **Read full docs**: See `README.md`
2. **Understand design**: See `IMPLEMENTATION.md`
3. **Run tests**: `pytest tests/ -v`
4. **Integrate**: Add to VS Code/Claude Desktop config above

## Questions?

Check files in this directory:
- Usage: `README.md`
- Architecture: `IMPLEMENTATION.md`
- Examples: `example_usage.py`
- Config: `mcp-config-example.json`
