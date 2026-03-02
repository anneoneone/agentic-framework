# Usage Guide

This guide covers day-to-day workflows with the copilot-agents framework: working with agents, creating and executing plans, managing knowledge, and monitoring performance.

## Agent Interaction

### Addressing agents

In VS Code Copilot chat, type `@` followed by the agent name:

```
@rust-expert explain the ownership pattern in this struct
@coordinator plan: add user authentication
@planner --review my-plan.json
```

Agents are only visible when you open the correct stack workspace.

### Agent discovery

Agents are discovered from `stacks/STACKNAME/.github/agents/`. Each stack workspace only shows its own agents plus any common/shared agents that have been symlinked in.

To find the best agent for a task programmatically:

```
agent-registry.find_agents_for_task(task_description="implement WebSocket handler", stack="live-moafunk")
```

### Creating agents

Use `@writer` to generate agents from a template:

```
@writer create-stack stacks/my-stack from /path with agents: @agent1, @agent2
```

Or update existing agents:

```
@writer --update my-stack
```

All agents follow the frontmatter schema (`framework/schemas/agent-frontmatter.schema.json`) with required fields: `name`, `description`, `version`, `keywords`.

### Validating agents

```bash
python framework/scripts/validate-agent.py --all           # All agents
python framework/scripts/validate-agent.py --stack my-stack  # One stack
```

Reports errors (must fix) and warnings (recommended improvements).

## Planning

### Creating plans

Delegate plan creation to `@planner` via `@coordinator`:

```
@coordinator plan: Add OCPP HeartBeat test with integration tests
```

`@planner` creates a v2.0 JSON plan in `stacks/<stack>/.copilot-agents/plans/` with steps, agent assignments, dependencies, parallel groups, and estimated tokens.

### Plan structure (v2.0)

Plans support hierarchical decomposition (max 2-level nesting):

```
Step 1 (sequential)
Step 2 (parallel group A)  ←─┐
Step 3 (parallel group A)  ←─┘  run together
  └── Step 3.1 (sub-step)
  └── Step 3.2 (sub-step)
Step 4 (depends on 2, 3)
```

Key schema fields: `parallel_group`, `priority` (critical/high/normal/low), `estimated_tokens`, `context_needed`, `mcp_tools`, `output`.

Full schema: `framework/schemas/plan-v2.schema.json`

### Reviewing plans

```
@planner --review my-plan.json
```

Runs a 6-item checklist: step atomicity, dependency completeness, agent assignments, parallel opportunities, token estimates, context coverage.

### Replanning

```
@planner --replan my-plan.json
```

8-step workflow that preserves completed steps and their knowledge while restructuring pending work.

## Execution

### Manual execution

Work through steps one by one, updating progress via `@coordinator`:

```
@coordinator show-plan                          # View current plan
@coordinator step 1 completed --summary "Done"  # Mark complete
@coordinator step 2 in progress                 # Mark active
@coordinator step 3 blocked: waiting for API    # Mark blocked
@coordinator step 4 skipped: not needed         # Skip step
@coordinator focus-on 3                         # Navigate to sub-plan
@coordinator focus-main                         # Back to top level
```

### Autonomous execution

Use the plan executor for API-driven execution:

```bash
# Dry-run: show schedule without calling APIs
python framework/scripts/plan-executor.py plan.json --mode dry-run

# Sequential: one step at a time via Messages API
python framework/scripts/plan-executor.py plan.json --mode sequential

# Batch: parallel waves via Batch API
python framework/scripts/plan-executor.py plan.json --mode batch

# Skip approval prompts for CI/headless use
python framework/scripts/plan-executor.py plan.json --mode sequential --auto-approve

# Resume from where you left off
python framework/scripts/plan-executor.py plan.json --mode sequential --resume
```

Steps with `priority: "critical"` or `"high"` require human approval by default (approve, skip, or abort).

### MCP-based execution

Agents can execute steps via the `plan-execution` MCP server:

```
plan-execution.execute_step(plan_path="plan.json", step_id="1")
plan-execution.execute_wave(plan_path="plan.json", wave_number=1)
plan-execution.get_execution_status(plan_path="plan.json")
plan-execution.resume_execution(plan_path="plan.json")
```

### Cross-stack execution

For plans spanning multiple stacks:

```bash
# Discover cross-stack dependencies
python framework/scripts/cross-stack-orchestrator.py discover

# Build unified schedule
python framework/scripts/cross-stack-orchestrator.py schedule plan1.json plan2.json

# Visualize dependency graph
python framework/scripts/cross-stack-orchestrator.py visualize plan1.json plan2.json
```

## Knowledge Management

### How knowledge is captured

Knowledge is extracted automatically from completed plan steps via `post-step-hook.py`. It captures decisions ("I chose X because..."), learnings ("Discovered that..."), blockers ("Blocked by..."), and notes.

Manual capture is also available:

```
@coordinator step 3 add-knowledge: WAL mode is 3x faster for reads
```

### Searching knowledge

Via `@coordinator`:

```
@coordinator search-knowledge "database migration"
```

Via MCP:

```
knowledge-search.search_knowledge(query="database migration", stack="live-moafunk")
knowledge-search.search_decisions(query="which ORM", stack="live-moafunk")
knowledge-search.search_cross_stack(query="authentication patterns")
```

### Building and maintaining indexes

```bash
# Build cross-stack index (run after major knowledge changes)
python framework/scripts/build-knowledge-index.py

# Compress old knowledge into summaries
python framework/scripts/compress-knowledge.py my-stack --report   # Preview
python framework/scripts/compress-knowledge.py my-stack            # Execute
python framework/scripts/compress-knowledge.py --all               # All stacks
```

### Exporting knowledge

```
@coordinator export-knowledge
```

Writes a markdown summary to `stacks/<stack>/.copilot-agents/knowledge/`.

## Monitoring and Optimization

### Token telemetry

Track token usage across plans and agents:

```bash
python framework/scripts/token-telemetry.py collect my-stack     # Collect from plans
python framework/scripts/token-telemetry.py report               # Summary report
python framework/scripts/token-telemetry.py dashboard            # Sparkline dashboard
python framework/scripts/token-telemetry.py agent-stats          # Per-agent breakdown
python framework/scripts/token-telemetry.py budget-accuracy      # Estimate vs actual
```

### Agent performance scoring

Composite scores based on success rate (40%), token efficiency (30%), output consistency (20%), and execution speed (10%):

```bash
python framework/scripts/agent-scoring.py leaderboard            # Ranked list
python framework/scripts/agent-scoring.py profile @rust-expert   # Detailed profile
python framework/scripts/agent-scoring.py recommend my-stack     # Improvement suggestions
```

### Cache tuning

Optimize MCP server cache TTLs based on file change frequency:

```bash
python framework/scripts/adaptive-cache.py analyze               # Scan change patterns
python framework/scripts/adaptive-cache.py recommend             # Suggest TTLs
python framework/scripts/adaptive-cache.py apply                 # Write config
python framework/scripts/adaptive-cache.py monitor --interval 3600  # Continuous
```

TTL categories: hot (>1 change/day → 1h), warm (weekly → 6h), cold (monthly → 24h), frozen (>30 days → 168h).

## Multi-Clone Support

Each stack has a `monorepo` symlink for pointing at different clones:

```bash
# Switch to a different clone
ln -snf /path/to/other/clone stacks/my-stack/monorepo

# Verify
ls -la stacks/my-stack/monorepo
```

## Troubleshooting

### Agents not appearing in Copilot chat

1. Check agents exist: `ls stacks/my-stack/.github/agents/`
2. Check workspace includes `.github/agents` path
3. Reload VS Code: Command Palette → "Developer: Reload Window"

### Validation errors

Run `python framework/scripts/validate-agent.py --all` and fix reported errors. Common issues: missing `version` field, missing `---` frontmatter delimiters.

### Plan execution fails

1. Check `ANTHROPIC_API_KEY` is set
2. Validate plan: `python framework/scripts/plan-executor.py plan.json --validate`
3. Try dry-run first: `python framework/scripts/plan-executor.py plan.json --mode dry-run`

### Knowledge search returns nothing

1. Run `python framework/scripts/build-knowledge-index.py` to rebuild the index
2. Check that JSONL files exist in `stacks/<stack>/docs/knowledge/`

## Reference

- [README.md](../README.md) — Framework overview
- [GETTING_STARTED.md](../GETTING_STARTED.md) — Setup walkthrough
- [framework/schemas/plan-v2.schema.json](../framework/schemas/plan-v2.schema.json) — Plan schema
- [framework/schemas/agent-frontmatter.schema.json](../framework/schemas/agent-frontmatter.schema.json) — Agent schema
- [framework/core/guidelines/GENERAL_RULES.md](../framework/core/guidelines/GENERAL_RULES.md) — Agent behavior rules
