# Task — Single Task with Enforced Knowledge Hooks

Execute a single task with the same pre/post knowledge hooks that plans get.
This is the enforced alternative to free-form `@coordinator <task>`.

## Input

`$ARGUMENTS` should be the task description, optionally prefixed with `--stack STACK` or `--agent @agent`.

Examples:
- `add a health check endpoint`
- `--stack live-moafunk fix the WebSocket reconnection bug`
- `--agent @axum-backend add rate limiting to the API`

## Workflow

This command enforces the 3-phase workflow via `task-executor.py`. Every phase runs regardless of task complexity.

### Phase 1: Pre-task

1. **Determine stack**: From `$ARGUMENTS` or ask the user
2. **Discover agent**: Use `agent-registry.find_agents_for_task()` unless `--agent` specified
3. **Fetch knowledge**: Query `memento-knowledge.search_knowledge_graph()` for relevant decisions/learnings
4. **Load agent context**: `memento-knowledge.get_agent_context()` for the chosen specialist
5. **Identify constraints**: Decisions that must not be contradicted

### Phase 2: Execute

Run the task via the specialist agent's system prompt + knowledge context:

```bash
python framework/scripts/task-executor.py \
  --stack <STACK> \
  --task "<TASK_DESCRIPTION>" \
  [--agent @<AGENT>] \
  [--model claude-sonnet-4-5-20250929] \
  [--context path/to/file]
```

The script:
- Loads the agent's `.agent.md` as system prompt
- Prepends constraints and learnings to the user message
- Calls the Anthropic Messages API
- Returns the specialist's response

### Phase 3: Post-task

1. **Extract knowledge**: Scan response for decision/learning language patterns
2. **Save to JSONL**: Write to `stacks/<stack>/docs/knowledge/tasks-YYYY-MM-DD.jsonl`
3. **Save to Neo4j**: Push decisions/learnings to memento-knowledge graph (if available)
4. **Report**: Show what was captured

### Dry-run

To preview without executing:
```bash
python framework/scripts/task-executor.py --stack <STACK> --task "<TASK>" --dry-run
```

### Rules

- **Never skip Phase 1 or Phase 3** — they run even for trivial tasks
- If Neo4j is unavailable, knowledge still gets saved to JSONL
- If no specialist is found, falls back to coordinator
- If the response contains no extractable knowledge, that's OK — don't force it
