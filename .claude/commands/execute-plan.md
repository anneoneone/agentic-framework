# Execute Plan

Execute plan steps with pre/post knowledge hooks.

## Input

`$ARGUMENTS` can be:
- Empty: execute the active plan in the current stack
- A plan file path: `stacks/<stack>/plans/<plan_id>.json`
- `--dry-run`: show execution schedule without running
- `--step <id>`: execute only a specific step

## Workflow

### Step 1: Load plan

Find the active plan:
- If path provided, use it directly
- Otherwise, find the most recent `active` plan in the current stack's `plans/` directory

Read the plan JSON and show current status:
```
plan-execution.get_execution_status(plan_path="<path>")
```

### Step 2: Dry-run check

If `--dry-run` is in arguments:
```
plan-execution.get_execution_schedule(plan_path="<path>", include_context=true)
```
Show the execution order with waves and stop.

### Step 3: Determine next steps

Identify which steps are ready to execute:
- Status is "pending"
- All dependencies are "completed" or "skipped"

If `--step <id>` specified, execute only that step.
Otherwise, propose the next ready step(s) and ask user for confirmation.

### Step 4: Pre-step knowledge fetch

Before executing each step, gather context:

1. **Plan-level context**: Load `context_sources` from the plan
2. **Step-level context**: Load `context_needed` from the step
3. **Memento query**: Search for relevant knowledge
   ```
   memento-knowledge.search_knowledge_graph(query="<step task keywords>", stack="<stack>")
   memento-knowledge.get_agent_context(agent="<step agent>", stack="<stack>")
   ```
4. Present relevant knowledge to inform the step execution

### Step 5: Execute step

For each step being executed:

1. Read the agent's `.agent.md` file to understand its role and constraints
2. Execute the task described in the step, acting as the assigned agent
3. Follow the agent's patterns, key files, and output format
4. Create/modify files as the task requires

After completing the work:
- Update step status to "completed" in the plan JSON
- Record output: summary, files_modified, files_created
- Update `token_budget.actual_total`
- Update `updated_at` timestamp

### Step 6: Post-step knowledge capture

After each step completion:

1. **Extract decisions**: Record any technical decisions made
   ```
   memento-knowledge.add_decision(
     content="<decision and reasoning>",
     stack="<stack>",
     plan_id="<plan_id>",
     step_id="<step_id>",
     agent="<step agent>"
   )
   ```

2. **Extract learnings**: Record discoveries or insights
   ```
   memento-knowledge.add_learning(
     content="<what was learned>",
     stack="<stack>",
     category="<category>",
     agent="<step agent>"
   )
   ```

3. **Update plan knowledge**: Add decisions/learnings to the step's `knowledge` object in the plan JSON

### Step 7: Continue or pause

After completing a step:
- Show updated progress
- If more steps are ready, ask if user wants to continue
- If all steps completed, mark plan `overall_status: "completed"` and suggest `/finalize`

### Rules

- Always ask before executing critical/high priority steps
- Never skip the pre-step knowledge fetch
- Always capture post-step knowledge
- Save plan JSON after every step completion (crash recovery)
- If a step fails or gets blocked, update status and ask user how to proceed
