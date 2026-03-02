# Copilot Agents Framework

A **stack-based multi-agent system** built on GitHub Copilot's `.agent.md` discovery mechanism. Each stack isolates domain-specific agents so only relevant agents appear in your workspace. The framework adds structured planning, knowledge management, and autonomous execution on top.

## Quick Start

| I want to... | Do this |
|-------------|---------|
| **Create a new stack** | `@analyzer /path/to/project` → `@writer create-stack ...` |
| **Plan a task** | `@coordinator plan: <task description>` |
| **Execute a plan** | `python framework/scripts/plan-executor.py <plan.json>` |
| **Search knowledge** | Use `knowledge-search` MCP server or `@coordinator search-knowledge <query>` |
| **Validate agents** | `python framework/scripts/validate-agent.py --all` |

See [GETTING_STARTED.md](GETTING_STARTED.md) for the full setup walkthrough.

## How It Works

### 1. Analyze → 2. Create Stack → 3. Plan → 4. Execute → 5. Learn

```
@analyzer scans codebase → recommends agents
   ↓
@writer generates stack (agents, workspace, docs)
   ↓
@planner creates structured JSON plan (v2.0 schema)
   ↓
@coordinator orchestrates execution (manual or autonomous)
   ↓
Knowledge auto-extracted → feeds future plans
```

### Agent Tiers

Agents live in three tiers, each with different scope:

- **Stack-specific** — `stacks/STACKNAME/.github/agents/` — domain experts for one project
- **Common** — `framework/core/common-agents/` — shared across all stacks (coordinator, gitlab, planner)
- **Shared knowledge** — `framework/core/shared-agents/` — domain expertise reusable across stacks
- **Meta-agents** — `framework/core/meta-agents/` — framework management (analyzer, writer)

## Repository Structure

```
copilot-agents/
├── framework/
│   ├── core/
│   │   ├── common-agents/          # @coordinator, @gitlab, @planner
│   │   ├── shared-agents/          # @ocpp-protocol, @documentation, etc.
│   │   ├── meta-agents/            # @analyzer, @writer
│   │   └── guidelines/             # GENERAL_RULES.md, TOKEN_EFFICIENCY.md
│   ├── mcp-servers/
│   │   ├── agent-registry/         # Agent discovery and capability mapping
│   │   ├── knowledge-search/       # TF-IDF/BM25 semantic knowledge search
│   │   └── plan-execution/         # Autonomous step execution via Anthropic API
│   ├── schemas/
│   │   ├── agent-frontmatter.schema.json
│   │   └── plan-v2.schema.json
│   ├── scripts/                    # 12 utility scripts (see below)
│   ├── knowledge/                  # Cross-stack knowledge index
│   ├── cache/                      # Adaptive cache TTL configs
│   ├── telemetry/                  # Token usage and agent scoring data
│   ├── templates/
│   │   └── specialist-template-v2.agent.md
│   └── architecture/               # Design docs
├── stacks/
│   ├── live-moafunk/               # Music streaming app stack
│   └── gartenroboter3000/          # Garden robot stack
├── .github/agents/                 # Root-level agent discovery
├── docs/                           # User guides
│   ├── usage-guide.md
│   ├── coordinator-usage.md
│   ├── multi-clone-setup.md
│   └── stack-map.md
├── GETTING_STARTED.md
├── TODO.md
└── IMPLEMENTATION_CHECKLIST.md
```

## Core Agents

| Agent | Role | MCP Servers |
|-------|------|-------------|
| `@analyzer` | Scans codebases, recommends agents | agent-registry |
| `@writer` | Generates complete stacks | filesystem, agent-registry |
| `@planner` | Creates v2.0 JSON plans with parallel groups | agent-registry, knowledge-search, plan-execution |
| `@coordinator` | Routes tasks, executes plans, tracks progress | agent-registry, plan-execution |
| `@gitlab` | GitLab workflow, commits, MRs | — |

## MCP Servers

Three custom MCP servers power the framework's automation layer:

**Agent Registry** — Agent discovery and capability mapping (5 tools: `list_agents`, `get_agent`, `find_agents_for_task`, `validate_agent`, `get_capability_map`). Keyword scoring with 24h TTL cache.

**Knowledge Search** — Semantic search over accumulated knowledge using TF-IDF/BM25 (6 tools: `search_knowledge`, `get_knowledge_entry`, `list_knowledge_files`, `search_decisions`, `search_cross_stack`, `resolve_context`). No external vector DB required.

**Plan Execution** — Autonomous plan step execution via Anthropic Messages and Batch APIs (6 tools: `execute_step`, `execute_wave`, `get_execution_schedule`, `get_execution_status`, `resume_execution`, `validate_plan_for_execution`). Includes human approval gates for critical steps.

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
      "agent": "@rust-expert",
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

```
# 1. Analyze your project
@analyzer /path/to/your/project

# 2. Generate the stack
@writer create-stack stacks/my-stack from /path with agents: @agent1, @agent2

# 3. Open the workspace
code stacks/my-stack/my-stack.code-workspace

# 4. Validate
python framework/scripts/validate-agent.py --stack my-stack
```

## Multi-Clone Support

Each stack has a `monorepo` symlink pointing at the active clone. Switch clones with:

```bash
ln -snf /path/to/other/clone stacks/my-stack/monorepo
```

See [docs/multi-clone-setup.md](docs/multi-clone-setup.md) for details.

## Knowledge System

The framework automatically captures and indexes knowledge from plan execution:

- **Extraction**: Decisions, learnings, blockers, and notes are pulled from completed plan steps
- **Indexing**: Cross-stack JSONL index with TF-IDF search (no external dependencies)
- **Compression**: Old knowledge is grouped by topic and compressed into hierarchical summaries
- **Integration**: Plans reference knowledge via `context_needed` fields, resolved at execution time

## Learn More

- [GETTING_STARTED.md](GETTING_STARTED.md) — Setup walkthrough and first steps
- [docs/usage-guide.md](docs/usage-guide.md) — Agent usage patterns and workflows
- [docs/coordinator-usage.md](docs/coordinator-usage.md) — Cross-stack coordination guide
- [framework/architecture/stack-architecture.md](framework/architecture/stack-architecture.md) — Architecture overview
- [TODO.md](TODO.md) — Implementation history (Phases 1-5 complete)

## License

SPDX-License-Identifier: LicenseRef-ebee-proprietary
Copyright: Bender Industries GmbH & co. KG and affiliates
