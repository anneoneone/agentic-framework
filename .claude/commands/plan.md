# Plan

Create a structured JSON execution plan for a complex task.

## Input

`$ARGUMENTS` contains the task description.

## Workflow

### Step 1: Determine stack

Identify which stack this plan belongs to:
- If currently working in a stack directory (`stacks/<name>/`), use that stack
- If the task mentions a specific stack, use that
- If ambiguous, ask the user

### Step 2: Check for active plans

Check if there's already an active plan in `stacks/<stack>/plans/`:
```bash
ls stacks/<stack>/plans/*.json 2>/dev/null
```
If an active plan exists (overall_status: "active"), warn the user and ask if they want to archive it first.

### Step 3: Discover available agents

Use the agent-registry MCP server to find agents:
```
agent-registry.list_agents(stack="<stack>")
agent-registry.get_capability_map(stack="<stack>")
```

If MCP unavailable, scan `stacks/<stack>/agents/*.agent.md` files and read their frontmatter.

### Step 4: Query existing knowledge

Check memento for relevant context:
```
memento-knowledge.search_knowledge_graph(query="<task keywords>", stack="<stack>")
```

### Step 5: Decompose task

Break the task into atomic steps following `framework/schemas/plan-v2.schema.json`:

- Each step has a single responsibility
- Assign the best-matching agent to each step
- Set dependencies between steps
- Identify steps that can run in parallel (assign `parallel_group`)
- Set priority: critical > high > normal > low
- Estimate tokens per step (500-2500 range)
- List required MCP tools per step
- Add `context_needed` for steps that need specific files or knowledge

### Step 6: Create plan JSON

Generate the plan following schema v2.0:
```json
{
  "schema_version": "2.0",
  "plan_id": "<YYYY-MM-DD_HH-mm-ss_task-slug>",
  "stack": "<stack>",
  "description": "<1-2 sentence objective>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",
  "overall_status": "active",
  "active_context": "main",
  "execution_mode": "sequential",
  "token_budget": {"estimated_total": <sum>, "actual_total": null},
  "steps": [...]
}
```

Write to: `stacks/<stack>/plans/<plan_id>.json`
Create the plans directory if needed.

### Step 7: Validate

Use the plan-execution MCP to validate:
```
plan-execution.validate_plan_for_execution(plan_path="stacks/<stack>/plans/<plan_id>.json")
```

### Step 8: Present

Show a condensed summary:
```
Plan created: <plan_id>

<N> steps, <N> agents, <N> parallel groups
Token budget: ~<N> estimated
Validation: [result]

Use /execute-plan to begin execution.
```

### Step 9: Record in knowledge

```
memento-knowledge.add_decision(
  content="Created plan <plan_id>: <description>",
  stack="<stack>",
  agent="@planner"
)
```
