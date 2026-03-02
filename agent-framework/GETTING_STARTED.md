# Getting Started

## Prerequisites

- Python 3.10+
- Anthropic API key (set via `ANTHROPIC_API_KEY` environment variable)
- git

## 1. Installation

### Step 1: Run the installer

```bash
./install.sh
```

This script:
- Creates a Python virtual environment
- Installs framework dependencies
- Validates the installation

### Step 2: Configure the framework

Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Optionally configure `framework/config.json`:

```json
{
  "model": "claude-opus-4-20250115",
  "default_stack": "default",
  "knowledge_dir": "stacks/*/agents/knowledge",
  "telemetry_enabled": true
}
```

## 2. Create Your First Stack

### Step 1: Analyze your project

Use the analyzer agent to scan your codebase:

```bash
agent-cli task analyzer /path/to/your/project
```

The analyzer detects patterns (languages, frameworks, domain concepts) and recommends agents.

### Step 2: Generate the stack

Based on the analyzer output, create the stack:

```bash
agent-cli invoke writer create-stack stacks/my-stack from /path/to/project
```

This creates the full directory structure:
- `stacks/my-stack/agents/` — domain specialists
- `stacks/my-stack/plans/` — JSON plans
- `stacks/my-stack/docs/` — documentation

### Step 3: Set up monorepo symlink

```bash
ln -snf /path/to/your/project stacks/my-stack/monorepo
```

### Step 4: Validate

```bash
python framework/scripts/validate-agent.py --stack my-stack
```

Expects 0 errors. Warnings about optional fields are fine.

### Step 5: Verify agents

```bash
agent-cli invoke analyzer stacks/my-stack/agents
```

Your stack agents are now ready.

## 3. Plan and Execute Tasks

The framework provides structured task planning and execution.

### Create a plan

```bash
agent-cli invoke coordinator plan "Add WebSocket handler for live updates"
```

This delegates to the planner, which creates a JSON plan with steps, agents, dependencies, and parallel groups.

### View the plan

```bash
agent-cli task coordinator show-plan stacks/my-stack/plans/latest.json
```

### Execute steps

**Manual** (step by step):

```bash
agent-cli invoke coordinator step 1 completed --summary "Implemented handler"
```

**Autonomous** (via CLI):

```bash
# Dry-run first
agent-cli plan stacks/my-stack/plans/my-plan.json --dry-run

# Execute sequentially
agent-cli plan stacks/my-stack/plans/my-plan.json --mode sequential

# Or parallel via Batch API
agent-cli plan stacks/my-stack/plans/my-plan.json --mode batch
```

Steps with `priority: "critical"` or `"high"` pause for human approval unless `--auto-approve` is set.

### Review and replan

```bash
agent-cli invoke coordinator review-plan stacks/my-stack/plans/my-plan.json
agent-cli invoke coordinator replan stacks/my-stack/plans/my-plan.json
```

## 4. MCP Server Setup (Optional)

Three MCP servers provide tool integration for agents. If you're using an MCP client, configure it as follows:

```json
{
  "mcpServers": {
    "agent-registry": {
      "command": "python",
      "args": ["framework/mcp-servers/agent-registry/server.py"],
      "cwd": "/path/to/agent-framework"
    },
    "knowledge-search": {
      "command": "python",
      "args": ["framework/mcp-servers/knowledge-search/server.py"],
      "cwd": "/path/to/agent-framework"
    },
    "plan-execution": {
      "command": "python",
      "args": ["framework/mcp-servers/plan-execution/server.py"],
      "cwd": "/path/to/agent-framework",
      "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```

Install dependencies:

```bash
pip install fastmcp anthropic
```

## 5. Knowledge Management

Knowledge is automatically captured from plan execution and stored as atomic JSONL entries.

### Search knowledge

```bash
agent-cli invoke coordinator search-knowledge "database migration patterns" --stack my-stack
```

Or use the MCP server:

```python
knowledge-search.search_knowledge(query="...", stack="my-stack")
```

### Build the cross-stack index

```bash
python framework/scripts/build-knowledge-index.py
```

Creates a unified index at `framework/knowledge/cross-stack-index.jsonl`.

### Compress old knowledge

```bash
python framework/scripts/compress-knowledge.py my-stack --report
python framework/scripts/compress-knowledge.py my-stack          # Actually compress
```

Groups related entries and creates topic-level summaries to reduce token costs.

## 6. Monitoring and Optimization

### Token telemetry

```bash
python framework/scripts/token-telemetry.py collect my-stack
python framework/scripts/token-telemetry.py dashboard
python framework/scripts/token-telemetry.py agent-stats
```

### Agent performance scoring

```bash
python framework/scripts/agent-scoring.py leaderboard
python framework/scripts/agent-scoring.py profile analyzer
python framework/scripts/agent-scoring.py recommend my-stack
```

### Cache tuning

```bash
python framework/scripts/adaptive-cache.py analyze
python framework/scripts/adaptive-cache.py recommend
python framework/scripts/adaptive-cache.py apply
```

## Architecture Overview

```
                    ┌──────────────┐
                    │  analyzer    │  Scans codebase
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   writer     │  Generates stack
                    └──────┬───────┘
                           ↓
    ┌──────────────────────────────────────────┐
    │              Stack                        │
    │  stacks/my-stack/agents/ → specialists   │
    │  stacks/my-stack/plans/ → JSON plans     │
    │  stacks/my-stack/docs/ → JSONL entries   │
    └──────────────┬───────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────┐
    │          Planning & Execution             │
    │  planner → creates JSON plans            │
    │  coordinator → routes & tracks           │
    │  agent-cli plan → autonomous execution   │
    └──────────────┬───────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────┐
    │          Knowledge & Optimization         │
    │  post-step-hook → auto-extract           │
    │  knowledge-search MCP → semantic queries │
    │  token-telemetry → usage tracking        │
    │  agent-scoring → performance metrics     │
    └──────────────────────────────────────────┘
```

## See Also

- [README.md](README.md) — Framework overview and full structure
- [docs/usage-guide.md](docs/usage-guide.md) — Detailed agent usage patterns
- [docs/coordinator-usage.md](docs/coordinator-usage.md) — Cross-stack coordination
- [docs/multi-clone-setup.md](docs/multi-clone-setup.md) — Multi-clone configuration
- [TODO.md](TODO.md) — Implementation history (Phases 1-5)
