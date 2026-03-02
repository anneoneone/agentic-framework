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

A stack represents one project (or monorepo) and contains its own domain-specialist agents, plans, and knowledge.

### Step 1: Analyze your project

Point the analyzer at your project root. It scans the codebase for languages, frameworks, and domain patterns, then recommends which agents to generate:

```bash
# Example: analyze a Rust + Vue.js live-streaming platform
python framework/scripts/agent-cli.py task "Analyze the codebase and recommend agents" \
  --stack live-moafunk

# Example: analyze a Raspberry Pi robotics project
python framework/scripts/agent-cli.py task "Analyze the codebase and recommend agents" \
  --stack gartenroboter3000
```

### Step 2: Generate the stack

Based on the analyzer output, create the stack and its agents:

```bash
python framework/scripts/agent-cli.py invoke writer \
  "Create stack live-moafunk with agents: axum-backend, vue-frontend, ffmpeg-pipeline, nginx-config"
```

This creates the full directory structure:

```
stacks/live-moafunk/
├── agents/
│   ├── axum-backend.agent.md       # Rust/Axum API specialist
│   ├── vue-frontend.agent.md       # Vue 3 + Vite frontend
│   ├── ffmpeg-pipeline.agent.md    # Media transcoding pipeline
│   ├── nginx-config.agent.md       # Reverse proxy / TLS
│   ├── coordinator.agent.md        # → symlink to framework/core/
│   └── planner.agent.md            # → symlink to framework/core/
├── plans/                          # JSON execution plans
└── docs/                           # JSONL knowledge entries
```

### Step 3: Set up monorepo symlink

Link the stack to the actual project source code:

```bash
ln -snf ~/projects/live-moafunk stacks/live-moafunk/monorepo
```

### Step 4: Validate

```bash
python framework/scripts/validate-agent.py --stack live-moafunk
```

Expects 0 errors. Warnings about optional fields (like `knowledge_sources`) are fine.

### Step 5: List and verify agents

```bash
# List all agents in the stack
python framework/scripts/agent-cli.py list --stack live-moafunk

# Output:
#   live-moafunk (6 agents):
#     axum-backend        Rust/Axum backend API specialist
#     vue-frontend        Vue 3 + Vite frontend specialist
#     ffmpeg-pipeline     FFmpeg media transcoding pipeline
#     nginx-config        Nginx reverse proxy configuration
#     coordinator         Cross-agent coordination and routing
#     planner             Task decomposition and plan generation
```

Your stack agents are now ready.

## 3. Plan and Execute Tasks

The framework decomposes tasks into multi-step plans, assigns agents, and executes them sequentially or in parallel via the Anthropic Batch API.

### Describe a task — the framework auto-selects the best agent

```bash
# The framework scores all available agents and picks the best match
python framework/scripts/agent-cli.py task \
  "Add rate limiting to the upload API — max 10 requests per minute per user" \
  --stack live-moafunk

# → Selects: axum-backend (score: 0.92)
# → Executes the task with the axum-backend agent's system prompt
```

### Invoke a specific agent directly

```bash
# Ask the Axum backend specialist to add a health endpoint
python framework/scripts/agent-cli.py invoke axum-backend \
  "Add a /health endpoint that returns 200 with JSON body {\"status\": \"ok\"}" \
  --stack live-moafunk

# Ask the Vue frontend specialist to fix a component
python framework/scripts/agent-cli.py invoke vue-frontend \
  "Fix the stream player component to handle HLS reconnection on network drop" \
  --stack live-moafunk
```

### Create a multi-step plan

For complex tasks that span multiple agents, create a plan:

```bash
python framework/scripts/agent-cli.py invoke coordinator \
  "Plan: Add WebSocket-based live chat to the streaming platform" \
  --stack live-moafunk
```

The planner decomposes this into steps with agents, dependencies, and parallel groups:

```json
{
  "steps": [
    {"id": 1, "agent": "axum-backend",  "task": "Add WebSocket upgrade handler at /ws/chat",  "group": "A"},
    {"id": 2, "agent": "axum-backend",  "task": "Implement chat room state and message fan-out", "group": "A"},
    {"id": 3, "agent": "vue-frontend",  "task": "Create ChatPanel.vue with message list and input", "group": "A"},
    {"id": 4, "agent": "nginx-config",  "task": "Add WebSocket proxy_pass for /ws/ location",  "group": "B", "depends_on": [1]},
    {"id": 5, "agent": "vue-frontend",  "task": "Integrate ChatPanel into stream viewer layout",  "group": "B", "depends_on": [3]}
  ]
}
```

### Execute the plan

```bash
# Dry-run first — shows what would happen without making API calls
python framework/scripts/agent-cli.py plan \
  stacks/live-moafunk/plans/add-live-chat.json --mode dry-run

# Execute steps sequentially (one at a time)
python framework/scripts/agent-cli.py plan \
  stacks/live-moafunk/plans/add-live-chat.json --mode sequential

# Execute in parallel waves via Anthropic Batch API (steps in same group run together)
python framework/scripts/agent-cli.py plan \
  stacks/live-moafunk/plans/add-live-chat.json --mode batch
```

Steps with `priority: "critical"` or `"high"` pause for human approval unless `--auto-approve` is set.

### Review and replan

```bash
python framework/scripts/agent-cli.py invoke coordinator \
  "Review plan stacks/live-moafunk/plans/add-live-chat.json" --stack live-moafunk
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
# Find entries about WebSocket patterns across the live-moafunk stack
python framework/scripts/agent-cli.py invoke coordinator \
  "Search knowledge: WebSocket connection handling patterns" \
  --stack live-moafunk

# Search across all stacks for database migration strategies
python framework/scripts/agent-cli.py invoke coordinator \
  "Search knowledge: database migration patterns"
```

Or use the MCP server directly from an MCP client:

```python
knowledge-search.search_knowledge(query="HLS stream reconnection", stack="live-moafunk")
```

### Build the cross-stack index

```bash
python framework/scripts/build-knowledge-index.py
```

Creates a unified index at `framework/knowledge/cross-stack-index.jsonl`, merging entries from all stacks (live-moafunk, gartenroboter3000, etc.).

### Compress old knowledge

```bash
# Preview what would be compressed
python framework/scripts/compress-knowledge.py live-moafunk --report

# Actually compress — groups related entries into topic-level summaries
python framework/scripts/compress-knowledge.py live-moafunk
```

Reduces token costs by consolidating repetitive entries (e.g., 12 entries about "Axum error handling" → 1 summary).

## 6. Monitoring and Optimization

### Token telemetry

```bash
# Collect usage data from the last plan execution
python framework/scripts/token-telemetry.py collect live-moafunk

# Show a dashboard with cost breakdown per agent and per step
python framework/scripts/token-telemetry.py dashboard

# Per-agent stats: avg tokens, cache hit rate, cost per invocation
python framework/scripts/token-telemetry.py agent-stats
```

### Agent performance scoring

```bash
# Global leaderboard — which agents produce the best results?
python framework/scripts/agent-scoring.py leaderboard

# Detailed profile for a specific agent
python framework/scripts/agent-scoring.py profile axum-backend

# Get recommendations for improving a stack's agents
python framework/scripts/agent-scoring.py recommend live-moafunk
```

### Cache tuning

```bash
# Analyze current cache efficiency across agents
python framework/scripts/adaptive-cache.py analyze

# Get recommendations for cache breakpoint adjustments
python framework/scripts/adaptive-cache.py recommend

# Apply the recommended cache settings
python framework/scripts/adaptive-cache.py apply
```

## Architecture Overview

```
                    ┌──────────────┐
                    │  analyzer    │  Scans your project (Rust, Vue, Python, …)
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   writer     │  Generates stack + domain agents
                    └──────┬───────┘
                           ↓
    ┌─────────────────────────────────────────────────┐
    │  Stack (e.g. live-moafunk)                       │
    │  stacks/live-moafunk/agents/                     │
    │    ├── axum-backend.agent.md                     │
    │    ├── vue-frontend.agent.md                     │
    │    ├── ffmpeg-pipeline.agent.md                  │
    │    └── coordinator.agent.md (→ symlink)          │
    │  stacks/live-moafunk/plans/  → JSON plans        │
    │  stacks/live-moafunk/docs/   → JSONL knowledge   │
    └──────────────┬──────────────────────────────────┘
                   ↓
    ┌─────────────────────────────────────────────────┐
    │  Planning & Execution                            │
    │  agent-cli task  → auto-select best agent        │
    │  agent-cli plan  → sequential or batch execution │
    │  Batch API       → parallel waves of steps       │
    └──────────────┬──────────────────────────────────┘
                   ↓
    ┌─────────────────────────────────────────────────┐
    │  Knowledge & Optimization                        │
    │  post-step-hook    → auto-extract learnings      │
    │  knowledge-search  → semantic queries (MCP)      │
    │  token-telemetry   → cost tracking per agent     │
    │  agent-scoring     → performance leaderboard     │
    └─────────────────────────────────────────────────┘
```

## See Also

- [README.md](README.md) — Framework overview and full structure
- [docs/usage-guide.md](docs/usage-guide.md) — Detailed agent usage patterns
- [docs/coordinator-usage.md](docs/coordinator-usage.md) — Cross-stack coordination
- [docs/multi-clone-setup.md](docs/multi-clone-setup.md) — Multi-clone configuration
- [TODO.md](TODO.md) — Implementation history (Phases 1-5)
