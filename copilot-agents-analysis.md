# Comprehensive Analysis: Copilot-Agents Agentic Framework

**Date**: February 26, 2026
**Scope**: Full project analysis, MCP server research, improvement roadmap

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [MCP Servers: Research & Recommendations](#3-mcp-servers-research--recommendations)
4. [Component ↔ MCP Server Mapping](#4-component--mcp-server-mapping)
5. [JSON Plan Mechanism: Improvements](#5-json-plan-mechanism-improvements)
6. [Agent Writer Reliability: Strict Patterns](#6-agent-writer-reliability-strict-patterns)
7. [Knowledge Management: Best Practices](#7-knowledge-management-best-practices)
8. [Centralized Agent Updates](#8-centralized-agent-updates)
9. [General Improvements](#9-general-improvements)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Executive Summary

Your framework is a **mature, production-tested** stack-based multi-agent system built around GitHub Copilot's `.agent.md` discovery mechanism. It successfully manages two active stacks (live-moafunk with 40+ completed plans, gartenroboter3000) and has solid foundations in hierarchical planning, token efficiency, and agent templates.

**Key Strengths:**
- Well-defined three-tier agent system (stack-specific, common, shared)
- Hierarchical JSON plan schema v1.1 with knowledge capture
- Aggressive token optimization (65-85% reduction targets)
- Real-world validation through extensive use
- Clean separation of concerns (analyzer → writer → planner → coordinator → specialists)

**Key Gaps Identified:**
- No programmatic orchestration — plan execution is manual (human types `@coordinator step N completed`)
- No vector/semantic search for knowledge — relies on grep and file-based caches
- No parallel execution mechanism — subtasks run sequentially through human interaction
- Knowledge sharing is primitive (SHARED_KNOWLEDGE.md files, no cross-stack queries)
- Writer agent produces inconsistent results — no schema validation of generated agents
- No versioning or change tracking for agents themselves
- Status enum inconsistency in plans (`"done"` vs `"completed"`)

---

## 2. Current Architecture Analysis

### 2.1 Framework Structure

```
copilot-agents/
├── framework/
│   ├── core/
│   │   ├── meta-agents/          # analyzer.agent.md, writer.agent.md
│   │   ├── common-agents/        # coordinator, planner, gitlab (symlinked into stacks)
│   │   ├── shared-agents/        # Cross-stack domain knowledge
│   │   └── guidelines/           # TOKEN_EFFICIENCY.md (910 lines)
│   ├── architecture/             # Docs about the framework itself
│   └── templates/                # specialist-agent.template.md, etc.
├── stacks/
│   ├── live-moafunk/             # Full-stack streaming platform
│   │   ├── .github/agents/       # 8 agents + 3 symlinks
│   │   ├── .copilot-agents/plans/  # 40+ plan JSON files
│   │   └── docs/SHARED_KNOWLEDGE.md
│   └── gartenroboter3000/        # Raspberry Pi garden automation
│       ├── .github/agents/       # 5 agents
│       └── docs/SHARED_KNOWLEDGE.md
└── docs/                         # Usage guides, coordinator reference
```

### 2.2 Agent Flow

```
User request
    ↓
@coordinator (route to stack/agent, or delegate to @planner)
    ↓
@planner (creates JSON plan with agent assignments)
    ↓
Human manually invokes each specialist agent per plan step
    ↓
Human manually updates plan status via @coordinator
    ↓
Knowledge captured in plan JSON
```

**Critical observation**: The loop between steps 4-6 is entirely manual. The human acts as the orchestration engine, which is the biggest bottleneck for autonomous operation.

### 2.3 Plan Schema v1.1 Analysis

**What works well:**
- Hierarchical decomposition (max 2-level nesting)
- Knowledge capture per step (decisions, learnings, blockers, references)
- Cross-stack plan linking via `related_plans`
- Artifact verification with timestamps
- Pre-flight validation (agent existence, dependency integrity)

**Issues found in actual plans:**
- Status enum inconsistency: `"done"` used in `fix-streaming-pipeline` plan vs `"completed"` in `admin-dashboard` plan. The schema says `"completed"` but real plans use both.
- Empty knowledge objects `{}` on most sub-steps — knowledge capture happens almost exclusively at the parent level
- No `estimated_tokens` or `estimated_duration` fields — makes batch planning impossible
- No `priority` field — all steps are equal, no way to express critical path
- No `parallel_group` field — no way to indicate which steps can run concurrently
- `artifacts` array is often empty even when files are clearly produced
- No `output` or `result` field to capture what the agent actually produced
- No `context_needed` field to specify what knowledge/files the agent needs as input

### 2.4 Agent Template Analysis

The specialist-agent.template.md is well-structured but:
- `{reference: path}` syntax is not a real include mechanism — it's a hint to the LLM
- No frontmatter schema validation (keywords field is optional, no required fields defined)
- No machine-readable capability declaration (just free-form markdown)
- The template references files that don't exist (e.g., `framework/templates/[DOMAIN]-examples.md`)

### 2.5 Token Efficiency

The TOKEN_EFFICIENCY.md guidelines are impressively thorough (910 lines), but:
- Token targets reference "baseline" numbers without a measurement mechanism
- No actual telemetry or tracking of token usage per invocation
- The guidelines assume GitHub Copilot's agent mode, which has different constraints than Claude/Anthropic API
- Cache TTL of 24h is hardcoded — no adaptive caching based on change frequency

---

## 3. MCP Servers: Research & Recommendations

### 3.1 Tier 1: Essential (Integrate Immediately)

#### Filesystem MCP Server
- **Source**: [modelcontextprotocol/servers/filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
- **Purpose**: Secure file operations with configurable directory access controls
- **Replaces**: Manual file reads in analyzer and writer agents
- **Integration**: Each stack gets its own filesystem scope. Agents access only their stack's files.

#### Git MCP Server
- **Source**: [modelcontextprotocol/servers/git](https://github.com/modelcontextprotocol/servers/tree/main/src/git)
- **Purpose**: Comprehensive git operations (clone, commit, branch, diff, log)
- **Replaces**: Your `@gitlab` common agent's manual git workflow
- **Integration**: Standardizes git operations across all stacks; replaces shell-based git commands

#### GitHub MCP Server (Official)
- **Source**: [github/github-mcp-server](https://github.com/github/github-mcp-server) (26K+ stars)
- **Purpose**: Full GitHub integration — repos, issues, PRs, code analysis
- **Replaces/Enhances**: `@gitlab` agent (for GitHub-based stacks like live-moafunk)
- **Integration**: Agent can analyze repos, create PRs, manage issues programmatically

#### Context Manager MCP Server
- **Source**: [tejpalvirk/contextmanager](https://github.com/tejpalvirk/contextmanager)
- **Purpose**: Persistent context across sessions using knowledge graphs; orchestrates domain-specific MCP servers
- **Replaces**: Your SHARED_KNOWLEDGE.md files and manual cross-stack knowledge queries
- **Integration**: Central knowledge hub that bridges all stacks

### 3.2 Tier 2: High Value (Integrate in Phase 2)

#### Memento MCP (Knowledge Graph)
- **Source**: [gannonh/memento-mcp](https://github.com/gannonh/memento-mcp)
- **Purpose**: Knowledge Graph Memory System using Neo4j backend with vector search
- **Enhances**: Cross-stack knowledge sharing with temporal awareness and multi-tenancy
- **Integration**: Each stack = one tenant; shared knowledge accessible across tenants

#### FastMCP Background Tasks
- **Source**: [gofastmcp.com/servers/tasks](https://gofastmcp.com/servers/tasks)
- **Purpose**: Background task execution with progress reporting, distributed processing
- **Enables**: Your goal of parallel subtask execution from JSON plans
- **Integration**: Plan executor dispatches steps as background tasks; monitors progress

#### RAG-MCP (Tool Selection)
- **Source**: [memoverflow/rag-mcp](https://github.com/memoverflow/rag-mcp)
- **Concept**: [arxiv.org/html/2505.03275v1](https://arxiv.org/html/2505.03275v1)
- **Purpose**: Vector-indexed tool/agent selection to avoid prompt bloat
- **Enhances**: Your agent discovery protocol — instead of scanning files, use vector similarity
- **Token savings**: Only relevant agents loaded into context per task

#### MCP Task Queue
- **Source**: [chriscarrollsmith/taskqueue-mcp](https://github.com/chriscarrollsmith/taskqueue-mcp)
- **Purpose**: Structured task queue with optional user approval checkpoints
- **Enables**: Automated plan execution with human-in-the-loop for critical steps

### 3.3 Tier 3: Specialized (Evaluate for Specific Stacks)

#### PostgreSQL/SQLite MCP Server
- **Purpose**: Direct database schema inspection and queries
- **Use case**: live-moafunk stack (SQLite), future stacks with databases
- **Integration**: Agents can query DB schema to inform code generation

#### Kubernetes MCP Server
- **Source**: [containers/kubernetes-mcp-server](https://github.com/containers/kubernetes-mcp-server)
- **Purpose**: 40+ tools for K8s resource management
- **Use case**: Docker-deploy agent in live-moafunk, future container-based stacks

#### Notion MCP Server (Official)
- **Source**: [developers.notion.com/docs/mcp](https://developers.notion.com/docs/mcp)
- **Purpose**: Read/update Notion pages, databases, comments
- **Use case**: Cross-stack knowledge if you use Notion for project management

### 3.4 Framework for Building Custom MCP Servers

#### FastMCP
- **Source**: [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)
- **Purpose**: Fast, Pythonic way to build MCP servers (powers 70% of all MCP servers)
- **Use case**: Build custom MCP servers for your domain-specific needs:
  - Plan execution server (reads JSON plans, dispatches to Anthropic batch API)
  - Knowledge graph server (wraps your SHARED_KNOWLEDGE system)
  - Agent registry server (manages agent discovery, versioning, updates)

### 3.5 Registries for Discovery

| Registry | URL | Notes |
|----------|-----|-------|
| Official MCP Registry | registry.modelcontextprotocol.io | Stable API (v0.1) |
| PulseMCP | pulsemcp.com/servers | 8,610+ servers, updated daily |
| Awesome MCP Servers | github.com/wong2/awesome-mcp-servers | Curated list |
| MCP Market | mcpmarket.com/leaderboards | Top 100 by GitHub stars |

---

## 4. Component ↔ MCP Server Mapping

### 4.1 Direct Replacements

| Current Component | Replace With | Benefit |
|-------------------|-------------|---------|
| `@gitlab` agent (manual git commands) | Git MCP + GitHub MCP servers | Programmatic git ops, no shell scripts |
| Agent discovery protocol (scan files, partial reads) | RAG-MCP + agent registry | Vector-based agent matching, faster, more accurate |
| SHARED_KNOWLEDGE.md files | Context Manager MCP + Memento MCP | Queryable knowledge graph, cross-stack search |
| Manual `grep_search` for code analysis | Filesystem MCP server | Standardized file access with scope controls |
| Manual plan execution (human-in-the-loop) | MCP Task Queue + FastMCP Background Tasks | Semi-automated execution with approval gates |

### 4.2 Enhancements (Add MCP Server Alongside Existing)

| Current Component | Enhance With | Benefit |
|-------------------|-------------|---------|
| `@analyzer` meta-agent | Filesystem MCP + GitHub MCP | Faster, more thorough codebase analysis |
| `@writer` meta-agent | Agent Registry MCP (custom) | Validates generated agents against schema |
| `@planner` agent | Task Queue MCP | Auto-dispatch plan steps as queued tasks |
| `@coordinator` routing | RAG-MCP | Semantic routing instead of keyword matching |
| Token efficiency guidelines | Telemetry MCP (custom) | Actual token usage tracking per agent/invocation |
| Cross-stack plan linking | Context Manager MCP | Automated dependency resolution across stacks |

### 4.3 New Capabilities via MCP

| New Capability | MCP Server | Impact |
|---------------|-----------|--------|
| Parallel subtask execution | FastMCP Background Tasks | Run independent plan steps concurrently |
| Anthropic batch API integration | Custom Plan Executor MCP | Submit entire plan as batch request |
| Persistent agent memory | Memento MCP | Agents remember past decisions across sessions |
| Database-aware agents | PostgreSQL/SQLite MCP | Agents can inspect and query DB schemas |
| Semantic knowledge search | Vector Search MCP | Find relevant knowledge without exact keyword match |

---

## 5. JSON Plan Mechanism: Improvements

### 5.1 Schema v2.0 Proposal

Based on analysis of 40+ actual plans and your goals for autonomous execution:

```json
{
  "schema_version": "2.0",
  "plan_id": "2026-02-26_14-00-00_feature-name",
  "stack": "live-moafunk",
  "description": "High-level objective",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601",
  "overall_status": "active",
  "active_context": "main",
  "related_plans": ["stack:plan_id"],

  "execution_mode": "sequential|parallel|batch",
  "batch_config": {
    "api": "anthropic",
    "model": "claude-sonnet-4-5-20250929",
    "max_concurrent": 5,
    "timeout_per_step_seconds": 300
  },

  "context_sources": [
    {"type": "file", "path": "docs/SHARED_KNOWLEDGE.md"},
    {"type": "mcp", "server": "context-manager", "query": "live-moafunk stack overview"},
    {"type": "plan", "plan_id": "related-plan-id", "extract": "knowledge"}
  ],

  "steps": [
    {
      "id": "1",
      "agent": "@axum-backend",
      "task": "Atomic task description",
      "dependencies": ["other-step-ids"],
      "parallel_group": "A",
      "priority": "critical|high|normal|low",
      "estimated_tokens": 1500,

      "context_needed": [
        {"type": "file", "path": "src/handlers/mod.rs", "reason": "understand existing handler pattern"},
        {"type": "knowledge", "query": "API endpoint conventions", "source": "stack"}
      ],

      "artifacts": [
        {
          "type": "file|test|manual|documentation",
          "path": "path/to/file",
          "verification": "exists|passes|manual|none",
          "verified_at": null,
          "auto_verified": false
        }
      ],

      "output": {
        "summary": null,
        "files_modified": [],
        "files_created": [],
        "tokens_used": null,
        "duration_seconds": null
      },

      "status": "pending|in-progress|completed|blocked|skipped",

      "sub_plan": null,

      "knowledge": {
        "decisions": [],
        "learnings": [],
        "references": [],
        "blockers_encountered": [],
        "notes": "",
        "agent_interactions": [],
        "ignored_knowledge": []
      },

      "mcp_tools": ["filesystem", "git"]
    }
  ]
}
```

### 5.2 Key Changes from v1.1 → v2.0

**New fields:**

| Field | Purpose | Why |
|-------|---------|-----|
| `execution_mode` | `sequential`, `parallel`, `batch` | Enables autonomous execution strategies |
| `batch_config` | Anthropic batch API configuration | Your goal: submit whole plan as batch |
| `context_sources` | Plan-level knowledge requirements | Reduces per-step context loading |
| `parallel_group` | Group ID for concurrent steps | Steps in same group run simultaneously |
| `priority` | Step importance level | Critical path identification |
| `estimated_tokens` | Expected token cost per step | Budget planning, batch optimization |
| `context_needed` | What the agent needs as input | Explicit context requirements reduce waste |
| `output` | Captured results from execution | Track what actually happened |
| `mcp_tools` | Which MCP servers this step needs | Tool provisioning for batch API |
| `status: "skipped"` | New status value | For steps that become unnecessary |

**Removed/Fixed:**

| Change | Reason |
|--------|--------|
| Fix `"done"` → `"completed"` | Status enum consistency (currently mixed in real plans) |
| Remove `active_context` from consideration for batch mode | Not needed when execution is automated |

### 5.3 Parallel Execution Groups

Steps with the same `parallel_group` and satisfied dependencies can run concurrently:

```json
{
  "steps": [
    {"id": "1", "task": "Add DB migration", "parallel_group": null, "dependencies": []},
    {"id": "2", "task": "Create backend handler", "parallel_group": "A", "dependencies": ["1"]},
    {"id": "3", "task": "Create frontend component", "parallel_group": "A", "dependencies": ["1"]},
    {"id": "4", "task": "Add API client method", "parallel_group": "A", "dependencies": ["1"]},
    {"id": "5", "task": "Integration test", "parallel_group": null, "dependencies": ["2", "3", "4"]}
  ]
}
```

Execution: `1` → (`2`, `3`, `4` in parallel) → `5`

### 5.4 Batch API Integration

For the Anthropic batch API, the plan executor would:

1. Read plan JSON
2. Identify steps with satisfied dependencies
3. For each executable step, construct a batch request:
   ```json
   {
     "custom_id": "plan_step_2",
     "params": {
       "model": "claude-sonnet-4-5-20250929",
       "max_tokens": 4096,
       "system": "<agent-definition-from-agent-file>",
       "messages": [
         {"role": "user", "content": "<task-description + context_needed content>"}
       ],
       "tools": ["<mcp_tools from step>"]
     }
   }
   ```
4. Submit batch, poll for completion
5. Parse results, update plan JSON with `output` field
6. Mark step completed, capture knowledge
7. Repeat for newly unblocked steps

### 5.5 Context Source Resolution

The `context_sources` and `context_needed` fields enable smart context loading:

```
Step requires: "understand API endpoint conventions"
    ↓
Resolver checks:
  1. SHARED_KNOWLEDGE.md → API Endpoints table (found, 200 tokens)
  2. Context Manager MCP → "API conventions for live-moafunk" (enriched, 150 tokens)
  3. Direct file read → src/handlers/mod.rs (relevant code, 300 tokens)
    ↓
Total context: 650 tokens (vs loading everything: 3000+ tokens)
```

---

## 6. Agent Writer Reliability: Strict Patterns

### 6.1 Problem Analysis

The `@writer` agent currently generates agents based on free-form markdown instructions with `{reference: path}` hints. This leads to:
- Inconsistent frontmatter (some agents have keywords, some don't)
- Varying section structures across generated agents
- Missing sections that the template specifies
- No validation that the generated agent is "correct"

### 6.2 Proposed: Agent Schema (machine-readable)

Create a JSON Schema that validates `.agent.md` frontmatter:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["name", "description", "keywords"],
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "Agent name (lowercase, kebab-case)"
    },
    "description": {
      "type": "string",
      "maxLength": 200,
      "description": "One-line specialist description"
    },
    "keywords": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3,
      "maxItems": 15,
      "description": "Discovery keywords for routing"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$",
      "description": "Agent version (major.minor)"
    },
    "scope": {
      "type": "object",
      "properties": {
        "primary": {"type": "array", "items": {"type": "string"}},
        "coordinate": {"type": "array", "items": {"type": "string"}},
        "out_of_scope": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["primary", "out_of_scope"]
    },
    "mcp_servers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Required MCP servers"
    }
  }
}
```

### 6.3 Proposed: Strict Section Structure

Every generated specialist agent MUST contain these sections in order:

```markdown
---
name: domain-expert
description: One-line description
keywords: [keyword1, keyword2, keyword3]
version: "1.0"
scope:
  primary: [task1, task2, task3]
  coordinate: [task4]
  out_of_scope: [task5, task6]
mcp_servers: [filesystem, git]
---

# Role
[2-3 sentences. WHO this agent is and WHAT it does.]

# Scope
- ✅ **Primary**: [3-5 items from frontmatter]
- ⚠️ **Coordinate**: [items requiring coordination]
- ❌ **Out of scope**: [items to delegate]

# Key Files
| File | Purpose |
|------|---------|
| `path/to/file1` | Description |
| `path/to/file2` | Description |

# Patterns
[3-5 common code patterns this agent should follow, with brief examples]

# Failure Modes
[3-5 common issues this specialist helps diagnose/fix]

# Output Format
[What this agent produces: code, configs, tests, docs]

# Efficiency
Target: <N tokens/invocation
- Check cache first: `.copilot-agents/knowledge/<domain>-patterns.md`
- grep before read
- Delegate out-of-scope immediately
```

### 6.4 Writer Validation Pipeline

After `@writer` generates an agent, run validation:

```
1. Parse YAML frontmatter → validate against JSON Schema
2. Check required sections exist (Role, Scope, Key Files, Patterns, Failure Modes, Output, Efficiency)
3. Verify Key Files paths exist in the target stack's codebase
4. Verify keywords don't overlap >50% with existing agents (prevents duplicates)
5. Check line count: 80-150 lines (too short = vague, too long = bloated)
6. Validate MCP server references against available servers
```

### 6.5 Writer `--update` Command

For updating agents after meta-agent changes (from your TODO):

```
@writer --update live-moafunk
```

This would:
1. Read all agents in the stack
2. Compare against current template version
3. For each agent:
   - Check frontmatter has all required fields
   - Check all required sections exist
   - Identify outdated efficiency guidelines
   - Generate diff showing what needs to change
4. Apply changes (with confirmation) or generate a migration plan

---

## 7. Knowledge Management: Best Practices

### 7.1 Current State

Your knowledge system consists of:
- `SHARED_KNOWLEDGE.md` per stack (flat markdown, manually maintained)
- Plan JSON files with embedded knowledge (decisions, learnings, references)
- `{reference: path}` syntax in agents (not a real include)
- 24h TTL cache for agent discovery
- Manual `export-knowledge` command that generates markdown summaries

### 7.2 Recommended Architecture: Three-Layer Knowledge

```
┌──────────────────────────────────────────────┐
│            Layer 3: Cross-Stack               │
│   Knowledge Graph (Memento/Context Manager)   │
│   - Entity relationships across stacks        │
│   - Shared design decisions                   │
│   - Common patterns and anti-patterns         │
└──────────────────────────────────────────────┘
                    ▲ queries
┌──────────────────────────────────────────────┐
│           Layer 2: Stack-Level                │
│   Structured JSONL + Vector Embeddings        │
│   - API endpoints, DB schemas, env vars       │
│   - Stack-specific patterns and conventions   │
│   - Plan knowledge (extracted automatically)  │
└──────────────────────────────────────────────┘
                    ▲ reads
┌──────────────────────────────────────────────┐
│          Layer 1: Session-Level               │
│   Working Memory (ephemeral)                  │
│   - Current plan context                      │
│   - Active step's knowledge                   │
│   - Recent agent interactions                 │
└──────────────────────────────────────────────┘
```

### 7.3 Immediate Improvement: Structured SHARED_KNOWLEDGE

Replace flat markdown with atomic, typed knowledge files:

```
stacks/live-moafunk/docs/knowledge/
├── api-endpoints.jsonl          # One endpoint per line
├── db-schema.jsonl              # One table per line
├── env-vars.jsonl               # One variable per line
├── patterns/
│   ├── rust-error-handling.md   # Atomic pattern doc
│   ├── vue-composable-pattern.md
│   └── api-handler-pattern.md
├── decisions/
│   ├── 2026-02-22_singleton-audio-capture.md
│   └── 2026-02-22_sqlite-settings-persistence.md
└── index.json                   # Machine-readable index
```

**JSONL format for API endpoints** (token-efficient):

```jsonl
{"method":"GET","path":"/api/stream/status","auth":false,"purpose":"Stream online status"}
{"method":"POST","path":"/api/auth/login","auth":false,"purpose":"Get auth token"}
{"method":"GET","path":"/api/artists","auth":true,"purpose":"List artists"}
```

**Benefits:**
- Machine-readable (agents can parse without LLM)
- Atomic (update one fact without rewriting everything)
- Searchable (grep for specific endpoints, patterns, decisions)
- Token-efficient (JSONL is 30-50% fewer tokens than markdown tables)

### 7.4 Automatic Knowledge Extraction Pipeline

After each plan step completes:

```
Agent response
    ↓
1. Extract decisions (regex: "chose X because", "using Y approach")
2. Extract learnings (regex: "discovered that", "found that")
3. Extract references (URLs, file paths)
4. Extract blockers (regex: "blocked by", "cannot proceed")
    ↓
5. Categorize by type (decision, learning, reference, blocker)
6. Write to plan JSON step.knowledge
    ↓
7. If decision is reusable → write to stack decisions/ folder
8. If pattern is new → write to stack patterns/ folder
9. If fact changes → update JSONL knowledge files
    ↓
10. Update cross-stack knowledge graph (if relevant to other stacks)
```

### 7.5 Cross-Stack Knowledge Queries

Implement a knowledge broker pattern:

```
Agent in Stack A: "What authentication pattern does the backend use?"
    ↓
Knowledge Broker:
  1. Check Stack A knowledge (local) → found: JWT auth with Bearer tokens
  2. If not found: Check cross-stack graph → search other stacks
  3. Return: "Stack A uses JWT Bearer tokens. Stack B uses API key auth."
    ↓
Agent receives only relevant context (minimal tokens)
```

### 7.6 Token-Efficient Knowledge Formats

Based on research, format selection has 40-70% impact on token usage:

| Format | Use When | Token Efficiency |
|--------|----------|-----------------|
| JSONL | Structured data (endpoints, schemas, variables) | Best for uniform data |
| Markdown | Human-readable docs (patterns, decisions) | Good balance |
| CSV | Relationship mappings, tabular data | Very efficient |
| TOON | Agent memory, entity indexes | 30-60% better than JSON |

**Avoid**: Large JSON objects with deep nesting. Prefer flat JSONL.

---

## 8. Centralized Agent Updates

### 8.1 Current Problem

- Common agents are symlinked from `framework/core/common-agents/` into stacks
- Stack-specific agents are individual files — no centralization
- When template changes, existing agents don't automatically update
- No versioning — can't tell if an agent is outdated

### 8.2 Proposed: Agent Registry

```
framework/
├── registry/
│   ├── agent-schema.json           # JSON Schema for frontmatter validation
│   ├── agent-versions.json         # Track current version per agent type
│   └── update-agents.sh            # Script to propagate updates
├── core/
│   ├── common-agents/              # (unchanged — symlinked)
│   └── shared-agents/              # (unchanged — symlinked)
└── templates/
    ├── specialist-agent.template.md  # Versioned template (v2.0)
    └── CHANGELOG.md                  # Template version history
```

**agent-versions.json:**

```json
{
  "template_version": "2.0",
  "common_agents": {
    "coordinator": {"version": "1.3", "hash": "abc123"},
    "planner": {"version": "1.2", "hash": "def456"},
    "gitlab": {"version": "1.0", "hash": "ghi789"}
  },
  "update_log": [
    {"date": "2026-02-26", "change": "Added mcp_servers to frontmatter schema", "version": "2.0"}
  ]
}
```

### 8.3 Update Propagation Script

```bash
#!/bin/bash
# update-agents.sh - Propagate framework changes to all stacks

for stack_dir in stacks/*/; do
  stack=$(basename "$stack_dir")
  echo "Updating stack: $stack"

  # 1. Update symlinks (common agents)
  for agent in framework/core/common-agents/*.agent.md; do
    agent_name=$(basename "$agent")
    target="$stack_dir/.github/agents/$agent_name"
    if [ -L "$target" ]; then
      ln -sf "$(realpath "$agent")" "$target"
      echo "  ✅ Updated symlink: $agent_name"
    fi
  done

  # 2. Validate stack-specific agents against schema
  for agent in "$stack_dir/.github/agents/"*.agent.md; do
    if [ ! -L "$agent" ]; then  # Skip symlinks
      # Parse frontmatter, validate against schema
      # Report missing fields, outdated sections
      echo "  ℹ️  Checking: $(basename "$agent")"
    fi
  done
done
```

### 8.4 Agent Versioning Strategy

Every agent gets a `version` field in frontmatter:
- **Major**: Breaking change (new required section, removed capability)
- **Minor**: Enhancement (new optional field, improved patterns)

When `@writer --update STACK` runs:
1. Compare each agent's version against template_version
2. For agents behind: generate specific diff showing what to add/change
3. Present changes for human approval
4. Apply approved changes and bump version

---

## 9. General Improvements

### 9.1 Status Enum Standardization

**Problem**: Plans use both `"done"` and `"completed"`. The schema says `"completed"` but some plans use `"done"`.

**Fix**: Add a migration script to normalize all existing plans:

```python
# normalize_plan_status.py
import json, glob

for plan_file in glob.glob("stacks/*/.copilot-agents/plans/*.json"):
    with open(plan_file) as f:
        plan = json.load(f)

    modified = False
    for step in plan.get("steps", []):
        if step.get("status") == "done":
            step["status"] = "completed"
            modified = True
        if "sub_plan" in step and step["sub_plan"]:
            for sub_step in step["sub_plan"].get("steps", []):
                if sub_step.get("status") == "done":
                    sub_step["status"] = "completed"
                    modified = True

    if modified:
        with open(plan_file, "w") as f:
            json.dump(plan, f, indent=2)
        print(f"Fixed: {plan_file}")
```

### 9.2 General Instructions File

From your TODO — create `framework/core/guidelines/GENERAL_RULES.md`:

```markdown
# General Rules for All Agents

## ALWAYS DO
- Create atomic documents (one topic per file)
- After code changes: verify stack documentation is current (update, add, or remove)
- Use consistent naming conventions (kebab-case for files, PascalCase for components)
- Reference knowledge cache before re-analyzing
- Provide sources for design decisions

## ASK FIRST
- Before creating new markdown documents
- Before modifying shared knowledge files
- Before changing agent boundaries or scope

## NEVER DO
- Write snapshot-like information without context (e.g., "50-60% reduction")
- Duplicate content across files (reference instead)
- Create agents without keyword definitions
- Skip validation steps
- Use absolute paths in workspace files
```

### 9.3 Atomic Shared Knowledge

From your TODO — shared knowledge files should be atomic:

**Before** (monolithic SHARED_KNOWLEDGE.md):
```markdown
# Shared Knowledge - live-moafunk
## API Endpoints [table with 20 endpoints]
## Database Schema [5 tables]
## Environment Variables [15 variables]
## Telegram Bot [detailed section]
## SoundCloud Integration [detailed section]
## Code Style [brief section]
## Git Workflow [brief section]
```

**After** (atomic files):
```
docs/knowledge/
├── api-endpoints.jsonl
├── db-schema.md
├── env-vars.jsonl
├── telegram-bot-integration.md
├── soundcloud-integration.md
├── code-style.md
├── git-workflow.md
└── index.md  (links to all files)
```

### 9.4 Agent Subcommands in Description

From your TODO — agent descriptions should show subcommands:

```yaml
---
name: planner
description: >
  Creates hierarchical JSON implementation plans.
  Commands: plan: <task>, --detailed, --validate-only
---
```

This allows GitHub Copilot to show available subcommands in the agent picker.

### 9.5 Anthropic Batch API Integration Design

For autonomous parallel execution:

```
Plan JSON
    ↓
Plan Executor (custom MCP server or script)
    ↓
1. Parse plan, build dependency graph
2. Identify steps with satisfied dependencies
3. Group by parallel_group
4. For each group:
   a. Load agent definition for each step
   b. Resolve context_needed (read files, query knowledge)
   c. Construct Anthropic Messages API request
   d. Add MCP tool definitions from step.mcp_tools
5. Submit as Anthropic Batch request
6. Poll for completion
7. Parse responses:
   a. Extract files created/modified
   b. Extract knowledge (decisions, learnings)
   c. Update plan JSON (status, output, knowledge)
8. Identify newly unblocked steps
9. Repeat from step 2
```

**Batch Request Format:**
```json
{
  "requests": [
    {
      "custom_id": "step_2",
      "params": {
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 8192,
        "system": "You are the @axum-backend specialist...",
        "messages": [
          {
            "role": "user",
            "content": "Task: Create backend handler for settings API.\n\nContext:\n- Existing handler pattern: [loaded from context_needed]\n- DB schema: [loaded from knowledge]\n\nArtifacts to produce:\n- src/handlers/settings.rs"
          }
        ]
      }
    },
    {
      "custom_id": "step_3",
      "params": { "..." }
    }
  ]
}
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (1-2 weeks)

**Goal**: Fix inconsistencies, establish strict patterns

1. **Normalize plan status enums** — run migration script for `"done"` → `"completed"`
2. **Create agent frontmatter JSON Schema** — enforce required fields
3. **Create GENERAL_RULES.md** — from your TODO items
4. **Split SHARED_KNOWLEDGE.md into atomic files** — per stack
5. **Add `version` field to all agent frontmatter** — start at "1.0"
6. **Add `keywords` field to all agents missing it** — required for discovery
7. **Writer `--update` command** — validate and update existing agents

### Phase 2: MCP Integration (2-3 weeks)

**Goal**: Replace manual operations with MCP servers

1. **Integrate Filesystem MCP server** — scope per stack
2. **Integrate Git MCP server** — replace shell-based git commands
3. **Integrate GitHub MCP server** — for GitHub-based stacks
4. **Build custom Agent Registry MCP** — using FastMCP framework
5. **Update agent discovery protocol** — use MCP instead of file scanning
6. **Add MCP server declarations to agent frontmatter** — `mcp_servers` field

### Phase 3: Knowledge Evolution (2-3 weeks)

**Goal**: Structured, queryable knowledge system

1. **Deploy local Qdrant instance** — vector storage for knowledge
2. **Build Knowledge MCP server** — wraps JSONL + vector search
3. **Implement automatic knowledge extraction pipeline** — from plan step completions
4. **Create cross-stack knowledge index** — entity disambiguation
5. **Replace `search-knowledge` command** — use semantic search
6. **Add `context_needed` field to plan schema** — explicit context requirements

### Phase 4: Autonomous Execution (3-4 weeks)

**Goal**: Semi-automated plan execution

1. **Upgrade plan schema to v2.0** — add parallel_group, priority, estimated_tokens, mcp_tools
2. **Build Plan Executor** — custom MCP server or standalone script
3. **Implement parallel execution groups** — dependency-aware scheduling
4. **Integrate Anthropic Batch API** — submit step groups as batch requests
5. **Build progress monitoring** — real-time plan status updates
6. **Add human approval gates** — for critical/destructive steps
7. **Implement result parsing** — extract outputs and knowledge from responses

### Phase 5: Optimization (Ongoing)

**Goal**: Continuous improvement

1. **Token telemetry** — measure actual usage per agent, per step
2. **Knowledge compression** — hierarchical summaries of old plans
3. **Agent performance scoring** — track success rate per agent type
4. **Adaptive caching** — adjust TTL based on change frequency
5. **Cross-stack plan orchestration** — automated dependency resolution

---

## Appendix A: MCP Server Installation Quick Reference

```bash
# Official servers (npm)
npx -y @modelcontextprotocol/server-filesystem /path/to/allowed/dir
npx -y @modelcontextprotocol/server-git

# GitHub MCP
gh extension install github/github-mcp-server

# FastMCP (Python - for building custom servers)
pip install fastmcp

# Memento (Knowledge Graph)
git clone https://github.com/gannonh/memento-mcp
cd memento-mcp && npm install

# Task Queue
npx -y taskqueue-mcp
```

## Appendix B: Key Research Sources

**MCP Ecosystem:**
- Official Registry: registry.modelcontextprotocol.io
- PulseMCP: pulsemcp.com/servers (8,610+ servers)
- GitHub MCP Server: github.com/github/github-mcp-server (26K+ stars)
- FastMCP: gofastmcp.com (powers 70% of MCP servers)

**Knowledge Management:**
- "Memory in the Age of AI Agents: A Survey" — arxiv.org/abs/2512.13564
- "From RAG to Agentic RAG to Agent Memory" — leoniemonigatti.com
- "Agent Memory: Filesystem vs Database" — leoniemonigatti.com
- "Collaborative Memory with Dynamic Access Control" — arxiv.org/html/2505.18279v1
- "GraphAgents for Cross-Domain Design" — arxiv.org/html/2602.07491
- Context Manager MCP — github.com/tejpalvirk/contextmanager

**Token Efficiency:**
- "Token Efficiency with Structured Output" — Microsoft Research
- "TOON: Token-Oriented Object Notation" — improvingagents.com
- "Reducing Token Usage of Software Engineering Agents" — TU Wien thesis
- "ACON: Agent Context Optimization" — 26-54% peak token reduction

**Agent Frameworks:**
- CrewAI vs LangGraph vs AutoGen comparison — datacamp.com
- "Designing Multi-Agent Intelligence" — Microsoft Developer Blog
- Agent-MCP Framework — github.com/rinadelph/Agent-MCP

**Batch/Parallel Execution:**
- FastMCP Background Tasks — gofastmcp.com/servers/tasks
- Anthropic Batch API — docs.anthropic.com/en/docs/build-with-claude/batch-processing
- MCP Task Queue — github.com/chriscarrollsmith/taskqueue-mcp
