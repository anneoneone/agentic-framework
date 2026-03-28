# Agent Framework v2

Stack-based multi-agent system for Claude Code. Each **stack** contains domain-specialist agents, execution plans, and a knowledge graph — all scoped to one project.

## Quick Start

```bash
# 1. Check that everything is set up
python framework/scripts/system-check.py

# 2. Create a stack for your project
/create-stack --link /path/to/your/repo --name my-project

# 3. Run a task
/task --stack my-project add a health check endpoint

# 4. Or plan something bigger
/plan --stack my-project migrate database layer to SQLAlchemy 2.0
/show-plan
/execute-plan
/knowledge-sync
/finalize
```

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://claude.ai/claude-code) with MCP support
- Neo4j (optional, for knowledge graph — falls back to JSONL)
- Anthropic API key (`ANTHROPIC_API_KEY` env var)

Install Python dependencies:

```bash
pip install -r requirements.txt
# or
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

## Project Structure

```
.claude/
  agents/                  → Meta-agents (analyzer, writer) — user-invokable
  commands/                → Slash commands: /task, /plan, /create-stack, etc.
framework/
  core/common-agents/      → coordinator, planner, gitlab (symlinked into stacks)
  core/shared-agents/      → Domain experts reusable across stacks
  core/guidelines/         → GENERAL_RULES.md, TOKEN_EFFICIENCY.md
  mcp-servers/             → agent-registry, knowledge-search, plan-execution, memento-knowledge
  scripts/                 → CLI tools (task-executor, plan-executor, etc.)
  schemas/                 → agent-frontmatter.schema.json, plan-v2.schema.json
  templates/               → specialist-agent.template.md
  knowledge/               → cross-stack-index.jsonl
stacks/
  <stack>/agents/          → Agent .md files (stack-specific + symlinks to common)
  <stack>/plans/           → JSON execution plans (v2.0 schema)
  <stack>/docs/knowledge/  → JSONL knowledge entries
  <stack>/.stack.json      → Repo link config (linked stacks only)
  <stack>/project/         → Symlink to external repo (linked stacks only)
```

## Concepts

### Stacks

A stack is a self-contained agent workspace for one project. Two types:

- **Linked** (recommended): Project source lives in an external repo. The stack contains only agents, plans, and knowledge. A `project/` symlink points to the external code.
- **Embedded** (legacy): Project source lives directly inside `stacks/<name>/`.

### Agents

Agent definitions are YAML frontmatter + markdown in `*.agent.md` files. Each agent is a domain specialist (e.g., `react-frontend`, `pdf-extractor`, `axum-backend`). Three common agents are shared across all stacks via symlinks:

- **coordinator** — Orchestrates tasks across specialists
- **planner** — Creates execution plans from task descriptions
- **gitlab** — Git/GitLab operations

### Knowledge

Every task and plan step captures knowledge (decisions, learnings) into:
- **JSONL files** in `stacks/<stack>/docs/knowledge/` (always available)
- **Neo4j graph** via memento-knowledge MCP server (optional, enables cross-stack search)

## Usage Examples

### Creating a Stack

```bash
# From an existing repo (creates a linked stack)
/create-stack --link /path/to/my-app --name my-app

# From a project description (interactive)
/create-stack "Real-time IoT dashboard with MQTT and React"

# Via guided interview
/create-stack --interview

# CLI equivalent
python framework/scripts/requirements-interview.py --output profile.json --create-stack
```

After creation, validate the generated agents:

```bash
/validate-agents --stack my-app
# or
python framework/scripts/validate-agent.py --stack my-app
```

### Running Single Tasks

The `/task` command enforces a 3-phase workflow: fetch knowledge → execute with specialist → capture knowledge.

```bash
# Auto-discovers the best agent for the task
/task --stack my-app add rate limiting to the API

# Force a specific agent
/task --agent @react-frontend fix the infinite re-render in Dashboard.tsx

# CLI equivalent
python framework/scripts/task-executor.py --stack my-app --task "add rate limiting to the API"

# Dry run (preview without executing)
python framework/scripts/task-executor.py --stack my-app --task "add rate limiting" --dry-run

# With extra context files
python framework/scripts/task-executor.py --stack my-app --task "fix auth bug" --context src/auth.py --context logs/error.log
```

### Planning and Executing Complex Tasks

For multi-step work, create a plan first:

```bash
# 1. Create a plan
/plan --stack my-app migrate from REST to GraphQL

# 2. Review the plan
/show-plan

# 3. Execute all steps (with knowledge hooks)
/execute-plan

# 4. Sync captured knowledge to the graph
/knowledge-sync

# 5. Lint, test, commit
/finalize
```

CLI alternatives for CI or scripting:

```bash
# Preview execution schedule
python framework/scripts/plan-executor.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --dry-run

# Execute a single step
python framework/scripts/plan-executor.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --step 1.1

# Execute all steps with auto-approve
python framework/scripts/plan-executor.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --auto-approve

# Batch execution via Anthropic Batches API
python framework/scripts/plan-executor.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --batch
```

### Knowledge Management

```bash
# Sync plan knowledge to JSONL + Neo4j
python framework/scripts/knowledge-sync.py stacks/my-app/plans/2026-03-10_migrate-graphql.json

# Sync a specific step only
python framework/scripts/knowledge-sync.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --step 2.1

# Import all existing knowledge for a stack into Neo4j
python framework/scripts/knowledge-sync.py --import-stack my-app

# Import knowledge for all stacks
python framework/scripts/knowledge-sync.py --import-all

# Dry run
python framework/scripts/knowledge-sync.py stacks/my-app/plans/2026-03-10_migrate-graphql.json --dry-run
```

### Token Telemetry

Track token usage across plan executions:

```bash
# Collect telemetry from all plan files
python framework/scripts/token-telemetry.py collect

# Generate a usage report
python framework/scripts/token-telemetry.py report
python framework/scripts/token-telemetry.py report --format json

# Compact dashboard with key metrics
python framework/scripts/token-telemetry.py dashboard

# Per-agent statistics
python framework/scripts/token-telemetry.py agent-stats
python framework/scripts/token-telemetry.py agent-stats --agent @react-frontend

# Budget accuracy: estimated vs actual tokens
python framework/scripts/token-telemetry.py budget-accuracy
```

### Agent Management

```bash
# Validate all agents across all stacks
python framework/scripts/validate-agent.py --all

# Validate agents in a specific stack
python framework/scripts/validate-agent.py --stack my-app

# Update agents to the latest template version
python framework/scripts/update-agents.py --all --dry-run
python framework/scripts/update-agents.py --stack my-app --fix

# Check system dependencies and MCP servers
python framework/scripts/system-check.py --verbose
```

### Linked Stack Management

```bash
# Restore all project/ symlinks (e.g., on a new machine)
python framework/scripts/link-stack.py --all

# Restore a specific stack's symlink
python framework/scripts/link-stack.py --stack my-app

# Check symlink health without making changes
python framework/scripts/link-stack.py --check
```

## MCP Servers

Four custom MCP servers power the framework:

| Server | Purpose |
|--------|---------|
| **agent-registry** | Agent discovery, validation, capability mapping |
| **knowledge-search** | TF-IDF/BM25 search across stack knowledge JSONL files |
| **plan-execution** | Execute/validate plan steps via Anthropic Messages API |
| **memento-knowledge** | Neo4j knowledge graph — decisions, learnings, cross-stack links |

External MCP servers (configured in `.mcp.json`):
- **filesystem** — File operations
- **git** — Git operations
- **context7** — Library documentation lookup
- **sequential-thinking** — Structured reasoning

## All Slash Commands

| Command | Purpose |
|---------|---------|
| `/task` | Execute a single task with enforced knowledge hooks |
| `/create-stack` | Analyze a project and create a new stack with agents |
| `/plan` | Create a JSON execution plan for a complex task |
| `/execute-plan` | Execute plan steps with pre/post knowledge hooks |
| `/show-plan` | Display plan status and progress |
| `/finalize` | Lint, test, commit after plan completion |
| `/validate-agents` | Validate agent files against schema |
| `/update-agents` | Update agents to current template version |
| `/knowledge-sync` | Sync plan knowledge to JSONL + Neo4j graph |
| `/token-telemetry` | Show token usage stats across plan executions |
| `/system-check` | Check dependencies, MCP servers, services |
