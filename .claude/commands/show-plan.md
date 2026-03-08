# Show Plan

Display the current plan status and progress.

## Input

`$ARGUMENTS` can be:
- Empty: show the active plan in the current stack
- A plan file path: `stacks/<stack>/plans/<plan_id>.json`
- `--full`: show full hierarchy including sub-steps

## Workflow

### Step 1: Find plan

If no path given, find the most recent plan in the current stack's `plans/` directory.

### Step 2: Display

Show the plan status using the plan-execution MCP:
```
plan-execution.get_execution_status(plan_path="<path>")
```

Format output as:
```
Plan: <plan_id> (<progress>% complete)
Stack: <stack>
Mode: <execution_mode>
Token budget: <actual>/<estimated>

Steps:
  ✓ 1. <task> (@agent)
  ✓ 2. <task> (@agent)
  → 3. <task> (@agent) [in-progress]
    3.1 <sub-task> (@agent)
    3.2 <sub-task> (@agent)
  · 4. <task> (@agent) [pending]
  · 5. <task> (@agent) [pending]

Next: Step 3 - @<agent>
```

Status icons:
- ✓ completed
- → in-progress
- ✗ blocked
- ○ skipped
- · pending
