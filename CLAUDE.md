# Agent Framework

Stack-based multi-agent system. Each stack contains domain-specialist agents for one project.

## Project structure

```
.claude/
  agents/                  → Meta-agents (analyzer, writer) - user-invokable
  commands/                → Slash commands: /create-stack, /plan, /execute-plan, /finalize, etc.
framework/
  core/common-agents/      → coordinator, planner, gitlab (symlinked into stacks)
  core/shared-agents/      → domain experts reusable across stacks
  core/guidelines/         → GENERAL_RULES.md, TOKEN_EFFICIENCY.md
  mcp-servers/             → agent-registry, knowledge-search, plan-execution, memento-knowledge
  scripts/                 → task-executor.py, plan-executor.py, knowledge-sync.py, validate-agent.py, update-agents.py, token-telemetry.py, system-check.py, requirements-interview.py
  schemas/                 → agent-frontmatter.schema.json, plan-v2.schema.json
  templates/               → specialist-agent.template.md
  knowledge/               → cross-stack-index.jsonl
stacks/
  STACKNAME/agents/        → agent .md files (stack-specific + symlinks to common)
  STACKNAME/plans/         → JSON execution plans (v2.0 schema)
  STACKNAME/docs/knowledge/ → JSONL knowledge entries
```

## Slash commands

| Command | Purpose |
|---------|---------|
| `/task` | Execute a single task with enforced pre/post knowledge hooks |
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

## MCP servers

Custom (in framework/mcp-servers/):
- **agent-registry** — Agent discovery, validation, capability mapping
- **knowledge-search** — TF-IDF/BM25 search across stack knowledge files
- **plan-execution** — Execute/validate plan steps via Anthropic Messages API
- **memento-knowledge** — Neo4j knowledge graph (decisions, learnings, cross-stack)

External (configured in .mcp.json):
- filesystem, git, context7, sequential-thinking

## Key conventions

- Agent definitions: YAML frontmatter + markdown body in `*.agent.md` files
- Plans: JSON files following `framework/schemas/plan-v2.schema.json`
- Knowledge: atomic JSONL entries in `stacks/STACKNAME/docs/knowledge/`
- Common agents are symlinked: `stacks/X/agents/coordinator.agent.md → framework/core/common-agents/coordinator.agent.md`
- Validate agents: `python framework/scripts/validate-agent.py --all`
- System check: `python framework/scripts/system-check.py`

## Task execution

Two paths — both enforce pre/post knowledge hooks:

### Single task (no plan)
```
/task <task description>
```
Runs: discover agent → fetch knowledge → execute with specialist → capture knowledge.
All 3 phases enforced by `task-executor.py`.

### Complex task (with plan)
```
/plan <task>  →  /show-plan  →  /execute-plan  →  /knowledge-sync  →  /finalize
```

CLI alternatives:
- `python framework/scripts/task-executor.py --stack STK --task "TASK" [--agent @name]`
- `python framework/scripts/plan-executor.py PLAN_FILE [--dry-run|--step ID|--batch]`
- `python framework/scripts/knowledge-sync.py PLAN_FILE [--dry-run|--import-stack STK]`
- `python framework/scripts/token-telemetry.py collect|report|dashboard|agent-stats|budget-accuracy`
- `python framework/scripts/update-agents.py [--stack STK|--all] [--fix] [--dry-run]`
- `python framework/scripts/requirements-interview.py [--output FILE] [--create-stack] [--dry-run]`

## When creating stacks or agents

- Use `/create-stack /path/to/project` or `/create-stack "project description"` or `/create-stack --interview`
- Stack dirs: `stacks/STACKNAME/{agents,plans,docs/knowledge}`
- Agent files go in `stacks/STACKNAME/agents/*.agent.md`
- Symlink common agents: `ln -sf ../../../framework/core/common-agents/coordinator.agent.md stacks/STACKNAME/agents/`
- Follow the template: `framework/templates/specialist-agent.template.md`
- Validate after creation: `python framework/scripts/validate-agent.py --stack STACKNAME`
