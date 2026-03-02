# Agent Framework

A **stack-based multi-agent system** powered by the Claude API. The framework orchestrates autonomous agents across different domains, each stack isolating domain-specific agents for focused execution. It provides structured planning, knowledge management, and autonomous execution via the Claude API's Messages and Batch endpoints.

## Quick Start

| I want to... | Do this |
|-------------|---------|
| **Install** | `./install.sh` then set `ANTHROPIC_API_KEY` environment variable |
| **Run an agent** | `python agent-cli.py task "your task description"` |
| **Plan a task** | `python agent-cli.py plan "describe what to do"` |
| **Invoke a specific agent** | `python agent-cli.py invoke --stack STACKNAME --agent AGENTNAME` |
| **Search knowledge** | `python agent-cli.py search "query"` |
| **Validate agents** | `python framework/scripts/validate-agent.py --all` |

See [GETTING_STARTED.md](GETTING_STARTED.md) for the full setup walkthrough.

## How It Works

### 1. Analyze → 2. Create Stack → 3. Plan → 4. Execute → 5. Learn

```
agent-cli analyzes codebase → recommends agents
   ↓
Generate stack (agents, configuration, docs)
   ↓
agent-cli plan creates structured JSON plan (v2.0 schema)
   ↓
agent-cli executes plan via Claude API (sequential or parallel)
   ↓
Knowledge auto-extracted → feeds future plans
```

### Agent Tiers

Agents live in three tiers, each with different scope:

- **Stack-specific** — `stacks/STACKNAME/agents/` — domain experts for one project
- **Common** — `framework/core/common-agents/` — shared across all stacks (coordinator, orchestrator, planner)
- **Shared knowledge** — `framework/core/shared-agents/` — domain expertise reusable across stacks
- **Meta-agents** — `framework/core/meta-agents/` — framework management (analyzer, writer)

## Repository Structure

```
agent-framework/
├── framework/
│   ├── core/
│   │   ├── common-agents/          # coordinator, orchestrator, planner
│   │   ├── shared-agents/          # domain-specific agents
│   │   ├── meta-agents/            # analyzer, writer
│   │   └── guidelines/             # GENERAL_RULES.md, TOKEN_EFFICIENCY.md
│   ├── mcp-servers/
│   │   ├── agent-registry/         # Agent discovery and capability mapping
│   │   ├── knowledge-search/       # TF-IDF/BM25 semantic knowledge search
│   │   └── plan-execution/         # Autonomous step execution via Claude API
│   ├── schemas/
│   │   ├── agent-frontmatter.schema.json
│   │   └── plan-v2.schema.json
│   ├── scripts/                    # Utility scripts (see below)
│   ├── knowledge/                  # Cross-stack knowledge index
│   ├── cache/                      # Adaptive cache TTL configs
│   ├── telemetry/                  # Token usage and agent scoring data
│   ├── templates/
│   │   └── specialist-template-v2.agent.md
│   └── architecture/               # Design docs
├── stacks/
│   ├── example-stack-1/            # Example stack
│   └── example-stack-2/            # Example stack
├── agent-cli.py                    # Main CLI entry point
├── install.sh                      # Installation script
├── docs/                           # User guides
│   ├── usage-guide.md
│   ├── orchestration-guide.md
│   └── stack-map.md
├── GETTING_STARTED.md
├── TODO.md
└── IMPLEMENTATION_CHECKLIST.md
```

## Core Agents

| Agent | Role | MCP Servers |
|-------|------|-------------|
| `analyzer` | Scans codebases, recommends agents | agent-registry |
| `writer` | Generates complete stacks | filesystem, agent-registry |
| `planner` | Creates v2.0 JSON plans with parallel groups | agent-registry, knowledge-search, plan-execution |
| `coordinator` | Routes tasks, executes plans, tracks progress | agent-registry, plan-execution |
| `orchestrator` | Orchestrates multi-stack execution | agent-registry, plan-execution |

## MCP Servers

Three custom MCP servers power the framework's automation layer:

**Agent Registry** — Agent discovery and capability mapping (5 tools: `list_agents`, `get_agent`, `find_agents_for_task`, `validate_agent`, `get_capability_map`). Keyword scoring with 24h TTL cache.

**Knowledge Search** — Semantic search over accumulated knowledge using TF-IDF/BM25 (6 tools: `search_knowledge`, `get_knowledge_entry`, `list_knowledge_files`, `search_decisions`, `search_cross_stack`, `resolve_context`). No external vector DB required.

**Plan Execution** — Autonomous plan step execution via Claude API Messages and Batch endpoints (6 tools: `execute_step`, `execute_wave`, `get_execution_schedule`, `get_execution_status`, `resume_execution`, `validate_plan_for_execution`). Includes human approval gates for critical steps.

## CLI Usage

### Task Mode

Execute a high-level task. The framework analyzes the task and dispatches to appropriate agents:

```bash
python agent-cli.py task "Add OAuth2 authentication to the user service"
```

### Plan Mode

Generate a detailed execution plan without running it:

```bash
python agent-cli.py plan "Refactor database schema for multi-tenancy"
```

Output: A JSON plan file with estimated tokens, parallel groups, and dependencies.

### Invoke Mode

Call a specific agent from a stack:

```bash
python agent-cli.py invoke --stack live-moafunk --agent rust-expert --task "Implement WebSocket handler"
```

## Scripts

| Script | Purpose |
|--------|---------|
| `validate-agent.py` | Validate all agents against frontmatter schema |
| `plan-executor.py` | Execute plans (sequential, batch, or dry-run) |
| `extract-knowledge.py` | Extract decisions/learnings from completed plans |
| `build-knowledge-index.py` | Build cross-stack knowledge index |
| `compress-knowledge.py` | Compress old knowledge into hierarchical summaries |
| `post-step-hook.py` | Auto-extract knowledge after each step completion |
| `migrate-plans-v2.py` | Migrate plans from v1.1 to v2.0 schema |
| `token-telemetry.py` | Track and report token usage per agent/step |
| `agent-scoring.py` | Score agent performance (success, efficiency, speed) |
| `adaptive-cache.py` | Tune MCP cache TTLs based on change frequency |
| `cross-stack-orchestrator.py` | Coordinate plan execution across stacks |
| `normalize-plan-status.py` | Normalize plan status values |

## Plan Schema v2.0

Plans are structured JSON files with hierarchical task decomposition:

```json
{
  "schema_version": "2.0",
  "plan_id": "2026-03-01_14-30-00_add-feature",
  "stack": "live-moafunk",
  "execution_mode": "parallel",
  "steps": [
    {
      "id": "1",
      "agent": "rust-expert",
      "task": "Implement WebSocket handler",
      "dependencies": [],
      "parallel_group": "A",
      "priority": "high",
      "estimated_tokens": 2000,
      "context_needed": [{"type": "knowledge", "query": "websocket patterns"}],
      "mcp_tools": ["filesystem"],
      "status": "pending"
    }
  ]
}
```

Key v2.0 features: parallel execution groups, priority-based scheduling, token budgeting, context resolution, step output capture, and Batch API support.

## Creating a Stack

```bash
# 1. Analyze your project
python agent-cli.py analyze /path/to/your/project

# 2. Generate the stack
python agent-cli.py create-stack stacks/my-stack \
  --source /path/to/project \
  --agents agent1,agent2,agent3

# 3. Validate
python framework/scripts/validate-agent.py --stack my-stack

# 4. Test with a sample task
python agent-cli.py invoke --stack my-stack --agent agent1 --task "Summarize the codebase"
```

## Configuration

The framework uses environment variables and config files:

```bash
# Required
export ANTHROPIC_API_KEY="sk-..."

# Optional
export CLAUDE_MODEL="claude-opus-4-20250115"  # Default model for all agents
export AGENT_FRAMEWORK_HOME="/path/to/agent-framework"
export LOG_LEVEL="INFO"
```

Stack-specific configuration goes in `stacks/STACKNAME/config.yaml`:

```yaml
name: my-stack
agents:
  - name: agent1
    model: claude-opus-4-20250115
    context_window: 200000
    temperature: 0.7
  - name: agent2
    model: claude-opus-4-20250115
    context_window: 200000
    temperature: 0.5
```

## Knowledge System

The framework automatically captures and indexes knowledge from plan execution:

- **Extraction**: Decisions, learnings, blockers, and notes are pulled from completed plan steps
- **Indexing**: Cross-stack JSONL index with TF-IDF search (no external dependencies)
- **Compression**: Old knowledge is grouped by topic and compressed into hierarchical summaries
- **Integration**: Plans reference knowledge via `context_needed` fields, resolved at execution time

## Learn More

- [GETTING_STARTED.md](GETTING_STARTED.md) — Setup walkthrough and first steps
- [docs/usage-guide.md](docs/usage-guide.md) — Agent usage patterns and workflows
- [docs/orchestration-guide.md](docs/orchestration-guide.md) — Multi-stack coordination guide
- [framework/architecture/stack-architecture.md](framework/architecture/stack-architecture.md) — Architecture overview
- [TODO.md](TODO.md) — Implementation history (Phases 1-5 complete)

## License

SPDX-License-Identifier: LicenseRef-ebee-proprietary
Copyright: Bender Industries GmbH & co. KG and affiliates
