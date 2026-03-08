# Stack: agentic-framework-v2

Self-referencing stack for developing the agent framework itself.

## Tech Stack
- Python 3.13, FastMCP 3.x, Anthropic Claude API, Neo4j (optional)
- JSON Schema 2020-12, YAML frontmatter, JSONL knowledge format

## Agents

### Specialist Agents
| Agent | Purpose |
|-------|---------|
| @python-backend | Framework scripts, CLI tools, orchestration logic |
| @mcp-specialist | MCP server development (FastMCP 3.x) |
| @schema-validator | JSON Schema, YAML frontmatter, agent templates |
| @knowledge-engineer | Neo4j graph, JSONL knowledge, cross-stack indexing |
| @testing | pytest, test coverage, fixtures and mocks |

### Common Agents (symlinked)
| Agent | Purpose |
|-------|---------|
| @coordinator | Task routing and plan execution |
| @planner | Plan creation and task decomposition |
| @gitlab | Git workflow automation |

## Directory Structure
```
stacks/agentic-framework-v2/
  agents/          — Agent definitions (5 specialist + 3 common symlinked)
  plans/           — JSON execution plans
  docs/knowledge/  — JSONL knowledge entries
```

## Usage
```bash
# Run a single task
python framework/scripts/task-executor.py --stack agentic-framework-v2 --task "description"

# Create and execute a plan
/plan <complex task>
/execute-plan
/knowledge-sync
/finalize
```
