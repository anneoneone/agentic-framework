# Getting Started

## Prerequisites

- VS Code with GitHub Copilot extension
- Python 3.10+ (for framework scripts and MCP servers)
- Optional: `ANTHROPIC_API_KEY` environment variable (for autonomous plan execution)

## 1. Choose Your Workspace

### Creating stacks (most users)

Open the main workspace to access `@analyzer` and `@writer`:

```bash
code copilot-agents.code-workspace
```

### Working within a stack

Open a stack workspace for domain-specific agents:

```bash
code stacks/live-moafunk/live-moafunk.code-workspace
```

Only agents relevant to that stack appear in Copilot chat.

## 2. Create Your First Stack

### Step 1: Analyze your project

```
@analyzer /path/to/your/project
```

The analyzer scans the codebase, detects patterns (languages, frameworks, domain concepts), and outputs a `@writer` command with recommended agents.

### Step 2: Generate the stack

Execute the command from the analyzer output:

```
@writer create-stack stacks/my-stack from /path/to/project with agents: @agent1, @agent2
```

This creates the full directory structure: agents, workspace file, docs, and knowledge directory.

### Step 3: Set up monorepo symlink

```bash
ln -snf /path/to/your/project stacks/my-stack/monorepo
```

### Step 4: Validate

```bash
python framework/scripts/validate-agent.py --stack my-stack
```

Expects 0 errors. Warnings about optional fields are fine.

### Step 5: Open and verify

```bash
code stacks/my-stack/my-stack.code-workspace
```

In Copilot chat, type `@` — your stack agents should autocomplete.

## 3. Plan and Execute Tasks

The framework provides structured task planning and execution.

### Create a plan

```
@coordinator plan: Add WebSocket handler for live updates
```

This delegates to `@planner`, which creates a JSON plan with steps, agents, dependencies, and parallel groups.

### View the plan

```
@coordinator show-plan
```

### Execute steps

**Manual** (step by step):

```
@coordinator step 1 completed --summary "Implemented handler"
```

**Autonomous** (via API):

```bash
# Dry-run first
python framework/scripts/plan-executor.py stacks/my-stack/.copilot-agents/plans/my-plan.json

# Execute for real
python framework/scripts/plan-executor.py my-plan.json --mode sequential

# Or parallel via Batch API
python framework/scripts/plan-executor.py my-plan.json --mode batch
```

Steps with `priority: "critical"` or `"high"` pause for human approval unless `--auto-approve` is set.

### Review and replan

```
@planner --review my-plan.json     # 6-item quality checklist
@planner --replan my-plan.json     # Rework plan preserving completed steps
```

## 4. MCP Server Setup

Three MCP servers provide tool integration for agents. Add them to your MCP client config:

```json
{
  "mcpServers": {
    "agent-registry": {
      "command": "python",
      "args": ["framework/mcp-servers/agent-registry/server.py"],
      "cwd": "/path/to/copilot-agents"
    },
    "knowledge-search": {
      "command": "python",
      "args": ["framework/mcp-servers/knowledge-search/server.py"],
      "cwd": "/path/to/copilot-agents"
    },
    "plan-execution": {
      "command": "python",
      "args": ["framework/mcp-servers/plan-execution/server.py"],
      "cwd": "/path/to/copilot-agents",
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

```
@coordinator search-knowledge "database migration patterns"
```

Or via MCP: `knowledge-search.search_knowledge(query="...", stack="my-stack")`

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
python framework/scripts/agent-scoring.py profile @rust-expert
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
                    │  @analyzer   │  Scans codebase
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   @writer    │  Generates stack
                    └──────┬───────┘
                           ↓
    ┌──────────────────────────────────────────┐
    │              Stack                        │
    │  .github/agents/ → domain specialists    │
    │  .copilot-agents/plans/ → JSON plans     │
    │  docs/knowledge/ → JSONL entries         │
    └──────────────┬───────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────┐
    │          Planning & Execution             │
    │  @planner → creates v2.0 plans           │
    │  @coordinator → routes & tracks          │
    │  plan-executor.py → autonomous execution │
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
