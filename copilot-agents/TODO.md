TODO:

- [x] Define agent commands at top of file → Added `## Commands` table to writer.agent.md v1.1
- [x] Agent description text shows subcommands (e.g. --plan Create a new plan) → Writer now documents `create-stack`, `--update STACK`, `--update --all`
- [x] writer: --update STACK which updates a certain stack after updating the meta-agents stack → Implemented in writer.agent.md v1.1 with 5-step Update Workflow
- [x] Create a general instructions file with general ruleset → Created `framework/core/guidelines/GENERAL_RULES.md` with ALWAYS DO / ASK FIRST / NEVER DO sections
  - [x] ALWAYS DO
    - [x] when creating documentation: create atomic documents
    - [x] after changing code: check if stack related documentation is up to date (update, add or remove docs)
  - [x] ASK FIRST
    - [x] before creating a new document, especially markdown docs
  - [x] NEVER DO
    - [x] write snapshot like information in docs (e.g. "50-60% reduction from baseline")
- [x] shared knowledge files should be atomic and have a very good title → Split both SHARED_KNOWLEDGE.md files into atomic docs under `docs/knowledge/`

## Completed in Phase 1 (not originally in TODO)

- [x] Agent frontmatter JSON Schema (`framework/schemas/agent-frontmatter.schema.json`)
- [x] Frontmatter added to all 19 agents (name, description, version, keywords, scope)
- [x] Plan status normalization: `done` → `completed` across 31 plan files (141 fixes)
- [x] Agent validation script (`framework/scripts/validate-agent.py`)
- [x] Specialist agent template v2.0 with validation pipeline and strict rules

## Completed in Phase 2

- [x] Integrate MCP servers into agent definitions → `mcp_servers` field added to all 21 agents
- [x] JSON Plan v2.0 schema with `parallel_group`, `priority`, `estimated_tokens` → `plan-v2.schema.json`
- [x] Agent Registry MCP server (5 tools: list_agents, get_agent, find_agents_for_task, validate_agent, get_capability_map)
- [x] Knowledge extraction pipeline (`extract-knowledge.py`) — 598 items from 31 plans
- [x] Plan executor scaffold with dependency resolver and batch request generation
- [x] Migrated all 31 plans from schema v1.1 to v2.0

## Completed in Phase 3

- [x] Knowledge Search MCP server (6 tools: search_knowledge, get_knowledge_entry, list_knowledge_files, search_decisions, search_cross_stack, resolve_context)
- [x] Cross-stack knowledge index aggregator (`build-knowledge-index.py`) — 2 stacks, 24 files, 674 entries
- [x] Post-step hook for automated knowledge extraction (`post-step-hook.py`)
- [x] Plan executor updated with context resolution for file, knowledge, plan_output, mcp_query
- [x] `@planner` subcommands: `--review` (6-item checklist), `--replan` (8-step workflow)
- [x] Knowledge auto-discovery: agents scan `docs/knowledge/` on startup with 24h TTL cache

## Completed in Phase 4

- [x] Plan Executor rewritten as full execution engine (sequential + batch + dry-run modes)
- [x] Anthropic Messages API integration for sequential step execution
- [x] Anthropic Batch API integration for parallel wave execution
- [x] Human approval gates for critical/high priority steps
- [x] Plan Execution MCP server (6 tools: execute_step, execute_wave, get_execution_schedule, get_execution_status, resume_execution, validate_plan_for_execution)
- [x] Progress monitoring with real-time display
- [x] Resume support for interrupted executions
- [x] `@coordinator` updated with autonomous execution commands

## Future TODO

- [ ] Token telemetry: measure actual usage per agent, per step (Phase 5)
- [ ] Knowledge compression: hierarchical summaries of old plans (Phase 5)
- [ ] Agent performance scoring: track success rate per agent type (Phase 5)
- [ ] Adaptive caching: adjust TTL based on change frequency (Phase 5)
- [ ] Cross-stack plan orchestration: automated dependency resolution (Phase 5)
