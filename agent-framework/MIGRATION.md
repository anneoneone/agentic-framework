# Migration Guide: Copilot Agents → Agent Framework

This guide covers the migration from the GitHub Copilot-based workflow to the standalone Claude API-based Agent Framework.

## What Changed

### Directory Rename
- `copilot-agents/` → `agent-framework/`

### Agent Location
- **Old:** `stacks/STACKNAME/.github/agents/*.agent.md`
- **New:** `stacks/STACKNAME/agents/*.agent.md`

The `.github/agents/` convention was specific to GitHub Copilot's discovery mechanism. The new `agents/` path is framework-agnostic.

### Agent Invocation
- **Old (Copilot chat):** `@coordinator plan: Add feature X`
- **New (CLI):** `python agent-cli.py task "Add feature X" --stack my-stack`

| Old (Copilot) | New (CLI) |
|---|---|
| `@coordinator plan: <task>` | `agent-cli task "<task>"` |
| `@agent-name <instruction>` | `agent-cli invoke <agent> "<instruction>"` |
| `@coordinator show-plan` | `agent-cli invoke coordinator "show-plan"` |
| `@coordinator execute-plan` | `agent-cli plan PLAN.json --mode sequential` |
| *(batch via MCP)* | `agent-cli plan PLAN.json --mode batch` |

### Configuration
- **Old:** VS Code `.code-workspace` files, Copilot extension settings
- **New:** `framework/config.json` + `ANTHROPIC_API_KEY` environment variable

### Workspace Files
The `.code-workspace` files are no longer required for agent discovery. They can still be used as IDE configuration but don't affect the framework.

## Migration Steps

1. **Rename the directory** (if not done already):
   ```bash
   mv copilot-agents agent-framework
   ```

2. **Move agent files** in each stack:
   ```bash
   cd agent-framework
   for stack in stacks/*/; do
     if [ -d "${stack}.github/agents" ]; then
       mkdir -p "${stack}agents"
       mv "${stack}.github/agents/"*.agent.md "${stack}agents/"
       # Recreate symlinks for common agents
       cd "${stack}agents"
       ln -sf ../../../framework/core/common-agents/coordinator.agent.md
       ln -sf ../../../framework/core/common-agents/gitlab.agent.md
       ln -sf ../../../framework/core/common-agents/planner.agent.md
       cd ../../..
     fi
   done
   ```

3. **Install the framework**:
   ```bash
   ./install.sh
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

4. **Verify**:
   ```bash
   python framework/scripts/agent-cli.py list
   python framework/scripts/validate-agent.py --all
   ```

## What Stayed the Same

- Agent `.agent.md` file format (YAML frontmatter + markdown body)
- Plan schema v2.0 (JSON format)
- Knowledge system (JSONL entries, TF-IDF/BM25 search)
- MCP servers (agent-registry, knowledge-search, plan-execution)
- All utility scripts in `framework/scripts/`
- Stack directory structure (stacks, plans, knowledge)
