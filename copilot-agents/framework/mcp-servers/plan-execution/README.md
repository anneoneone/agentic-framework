# Plan Execution MCP Server

Provides tools for executing and monitoring plan steps via the Anthropic Messages API. Wraps the plan-executor functionality as MCP tools that can be called by agents (especially @coordinator).

## Overview

This MCP server enables programmatic execution of implementation plans defined in the v2.0 schema. It supports:

- Single step execution via Messages API
- Parallel wave execution via Batch API
- Execution scheduling and dependency resolution
- Plan validation and status tracking
- Context loading from knowledge bases and files

## Tools

### `execute_step`

Execute a single plan step using the Anthropic Messages API.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON file
- `step_id` (string, required): Step ID to execute
- `model` (string, optional): Model override (default: from plan's batch_config or claude-sonnet-4-5-20250929)
- `max_tokens` (integer, optional): Max tokens for response (default: 4096)
- `dry_run` (boolean, optional): If true, show what would be sent without calling API

**Returns:**
```json
{
  "step_id": "step-1",
  "status": "completed",
  "summary": "Task completed successfully...",
  "tokens_used": 1234,
  "files_modified": [],
  "files_created": [],
  "duration_seconds": 5.2,
  "timestamp": "2026-03-02T10:30:45.123456"
}
```

**Implementation Details:**
- Loads plan JSON (handles trailing commas with regex)
- Finds step by ID (handles hierarchical steps with sub_plan)
- Reads agent's .agent.md file to get system prompt
- Resolves context_needed for the step
- Builds messages array with task + context
- Calls `anthropic.Anthropic().messages.create()`
- Parses response and extracts summary
- Updates plan JSON (step status, output field, token_budget)
- Saves updated plan back to disk

### `execute_wave`

Execute a parallel group of steps via Batch API.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON
- `parallel_group` (string, optional): Execute specific parallel group
- `wave_number` (integer, optional): Execute specific wave number
- `model` (string, optional): Model override
- `dry_run` (boolean, optional): Show batch request without submitting

**Returns:**
```json
{
  "wave_number": 0,
  "steps": [
    {
      "step_id": "step-1",
      "status": "completed",
      "summary": "...",
      "tokens_used": 1000,
      ...
    }
  ],
  "batch_id": "batch_abc123",
  "total_tokens": 2500,
  "total_duration_seconds": 12.3
}
```

**Implementation Details:**
- Loads plan, resolves dependencies into waves
- If parallel_group specified, finds matching wave; otherwise uses wave_number
- Builds batch request array
- Submits via `client.beta.messages.batches.create()`
- Polls for results (30s interval, configurable timeout)
- Parses results, updates plan steps
- Returns aggregated results

### `get_execution_schedule`

Show the planned execution order without running anything.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON file
- `include_context` (boolean, optional): Include resolved context info
- `include_completed` (boolean, optional): Include already-completed steps

**Returns:**
```json
{
  "waves": [
    {
      "wave_number": 0,
      "steps": [
        {
          "id": "step-1",
          "task": "Initialize project structure...",
          "agent": "setup-agent",
          "status": "pending",
          "priority": "high",
          "parallel_group": "initialization",
          "dependencies": [],
          "estimated_tokens": 2000,
          "context_needed": { ... }
        }
      ]
    }
  ]
}
```

### `get_execution_status`

Get current execution progress for a plan.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON file

**Returns:**
```json
{
  "overall_status": "active",
  "progress_percentage": 45.5,
  "completed_steps": ["step-1", "step-2"],
  "pending_steps": ["step-3", "step-4"],
  "blocked_steps": {
    "step-5": ["step-3"]
  },
  "token_budget": {
    "limit": 50000,
    "actual_total": 12340
  },
  "next_executable_steps": ["step-3", "step-4"],
  "critical_path_status": "on_track"
}
```

### `resume_execution`

Resume plan execution from where it left off.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON file
- `mode` (string, optional): "sequential" or "batch" (default: from plan's execution_mode)
- `auto_approve` (boolean, optional): Skip approval for all steps

**Returns:**
```json
{
  "completed_steps": 5,
  "failed_steps": 0,
  "total_tokens_used": 25000,
  "duration_seconds": 125.4,
  "steps_results": [
    { ... step result ... }
  ]
}
```

### `validate_plan_for_execution`

Check if a plan is ready for execution.

**Parameters:**
- `plan_path` (string, required): Path to plan JSON file

**Returns:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Agent 'special-agent' not found in any location"
  ],
  "agents_found": [
    "setup-agent",
    "implementation-agent",
    "testing-agent"
  ],
  "estimated_cost": 50000
}
```

**Validation Checks:**
- Schema version is 2.0
- Required fields present (plan_id, stack, description, steps)
- All agents referenced in steps are found
- No circular dependencies
- Context sources are accessible

## Agent File Discovery

The server searches for agent files in these locations:

1. `stacks/<stack>/.github/agents/<agent-name>.agent.md`
2. `framework/core/common-agents/<agent-name>.agent.md`
3. `framework/core/shared-agents/<agent-name>.agent.md`
4. `framework/core/meta-agents/<agent-name>.agent.md`

## Plan File Format

Plans must conform to the plan-v2.schema.json:

```json
{
  "schema_version": "2.0",
  "plan_id": "2026-03-02_10-30-45_initialize-project",
  "stack": "my-stack",
  "description": "Set up project structure and initialization",
  "created_at": "2026-03-02T10:30:45Z",
  "updated_at": "2026-03-02T10:30:45Z",
  "overall_status": "active",
  "active_context": "main",
  "execution_mode": "sequential",
  "batch_config": {
    "model": "claude-sonnet-4-5-20250929",
    "max_concurrent": 5,
    "timeout_seconds": 300
  },
  "steps": [
    {
      "id": "step-1",
      "task": "Initialize project",
      "agent": "setup-agent",
      "status": "pending",
      "priority": "high",
      "parallel_group": "initialization",
      "dependencies": [],
      "estimated_tokens": 2000,
      "context_needed": {
        "knowledge": ["project structure templates"],
        "files": ["docs/setup-guide.md"]
      }
    }
  ],
  "token_budget": {
    "limit": 100000,
    "actual_total": 0
  }
}
```

## Environment Variables

- `ANTHROPIC_API_KEY` (required): API key for Anthropic API access. Validated when tools are called, not at startup.

## Implementation Notes

### Error Handling

- Missing plan files return "File not found" errors
- Invalid JSON is handled by cleaning trailing commas with regex
- Invalid agents return "Agent not found" errors
- API errors are caught and returned as step error status
- Circular dependencies are detected and reported

### Context Resolution

The `context_needed` field in steps can reference:

- **knowledge**: Search queries for knowledge bases
- **files**: Relative file paths to include
- **plan_outputs**: References to previous step outputs
- **mcp_queries**: Calls to other MCP servers

### Plan Updates

Each successful step execution updates the plan JSON:
- Step `status` → "completed" or "error"
- Step `output` → response summary
- Step `completed_at` → ISO 8601 timestamp
- Step `tokens_used` → actual token count
- Plan `token_budget.actual_total` → cumulative tokens
- Plan `updated_at` → current timestamp

### Caching

- Agent file reads are cached with 24-hour TTL
- Plan dependencies are resolved fresh on each call (no caching)
- Index builds are cached but invalidated on plan updates

## Usage Examples

### Execute a single step

```python
# Tool call
{
  "name": "execute_step",
  "arguments": {
    "plan_path": "/path/to/plan.json",
    "step_id": "step-1",
    "dry_run": false
  }
}
```

### Preview execution schedule

```python
# Tool call
{
  "name": "get_execution_schedule",
  "arguments": {
    "plan_path": "/path/to/plan.json",
    "include_context": true
  }
}
```

### Validate before executing

```python
# Tool call
{
  "name": "validate_plan_for_execution",
  "arguments": {
    "plan_path": "/path/to/plan.json"
  }
}
```

### Check progress

```python
# Tool call
{
  "name": "get_execution_status",
  "arguments": {
    "plan_path": "/path/to/plan.json"
  }
}
```

## Architecture

### Server Structure

```
server.py              # Main MCP server implementation
├── Data Models       # StepResult, WaveResult, ExecutionStatus, ValidationResult
├── Plan Loading      # load_plan, parse_frontmatter, find_agent_file
├── Execution         # execute_step_with_api, update_plan_step
├── Utilities         # resolve_context_needed, flatten_steps, resolve_dependencies
└── MCP Handlers      # list_tools, call_tool
```

### Key Functions

- `load_plan()` - Load JSON with trailing comma cleanup
- `find_agent_file()` - Search agent file locations
- `get_agent_system_prompt()` - Extract frontmatter from agent
- `resolve_dependencies()` - Build execution waves from DAG
- `execute_step_with_api()` - Single step execution
- `update_plan_step()` - Persist results back to plan JSON

## Related Files

- `/framework/scripts/plan-executor.py` - Original scaffold (reference)
- `/framework/schemas/plan-v2.schema.json` - Plan format specification
- `/framework/core/common-agents/` - Built-in agents
- MCP Servers: `agent-registry`, `knowledge-search`
