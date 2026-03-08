# Stack Creation Template

This template shows the exact stack-local structure and workspace path pattern to follow when creating new stacks.

## Directory Structure

```
stacks/[STACKNAME]/
├── agents/                         # Stack-specific agent files (discoverable)
│   ├── [agent1].agent.md           # Actual file (created by @writer)
│   ├── [agent2].agent.md           # Actual file (created by @writer)
│   └── ...
├── docs/
│   └── SHARED_KNOWLEDGE.md         # Stack integration documentation
├── README.md                        # Stack overview
├── monorepo -> /path/to/monorepo    # Symlink created by user commands
└── [STACKNAME].code-workspace      # VS Code workspace
```

## Workspace Configuration

The workspace must include the stack folder root `.` so `agents/` is discoverable.

Important: do not use `~` or `${userHome}` in `folders[].path` because VS Code may treat them as literal text.
Use workspace-relative paths instead.

```json
{
  “folders”: [
    {
      “name”: “🤖 Agents ([STACKNAME])”,
      “path”: “agents”
    },
    {
      “name”: “📦 Main Service”,
      “path”: “monorepo/[path-to-service]”
    },
    {
      “name”: “📚 Stack ([STACKNAME])”,
      “path”: “.”
    }
    // ... other folders
  ],
  “settings”: {
    // Stack-specific settings
  }
}
```

## Why This Pattern?

**Agent Discovery:**
- Agents are discovered from `agents/` under a workspace folder root
- The stack root `.` contains `agents`, so discovery works without global symlinks

**Workspace Robustness:**
- Avoids fragile `${userHome}`/`~` expansion in `.code-workspace`
- Avoids relying on `${env:...}` expansion for `folders[].path` by using a stack-local `monorepo/` symlink

**Stack Isolation:**
- The “🤖 Agents” folder points at `agents`, so Explorer shows only this stack’s agents

## Example: Creating a Python Testing Stack

```bash
# 1. Use @analyzer to understand the Python test codebase
@analyzer ${env:EBEE_MONOREPO_ROOT}/tests/python

# 2. Get agent recommendations
# Output includes: @writer command

# 3. Execute @writer with recommended agents
@writer create-stack stacks/python-test from tests/python with agents: @pytest-expert, @python-tools, @async-patterns

# 4. User executes generated shell commands:
#    - Creates stacks/python-test/{agents,docs}
#    - Creates agent files
#    - Creates symlinks in monorepo
#    - Creates workspace file
#    - Creates documentation

# 5. User opens workspace
code ~/agent-framework/stacks/python-test/python-test.code-workspace

# 6. Agents are discovered from agents/
#    Both stack-specific and common/shared agents appear
```

## Checklist for New Stacks

- [ ] Directory structure created: `stacks/[STACKNAME]/{agents,docs}`
- [ ] Agent files created in `stacks/[STACKNAME]/agents/`
- [ ] `stacks/[STACKNAME]/monorepo` symlink created
- [ ] Workspace folders use only relative paths (`.`, `agents`, `monorepo/...`)
- [ ] SHARED_KNOWLEDGE.md created with integration points
- [ ] README.md created with stack overview
- [ ] Documentation updated with new stack reference
