# Stack-Based Architecture

This repository organizes agents by stack/workspace to ensure **filtered agent availability** - when you open the OCPP workspace, you only see OCPP-relevant agents.

## Directory Structure

```
agent-framework/
├── framework/                  # 🏗️ Reusable framework components
│   ├── core/                   # Agent storage
│   │   ├── common-agents/      # Agents available in ALL stacks (symlinked)
│   │   │   ├── coordinator.agent.md  # Routes queries across stacks
│   │   │   └── gitlab.agent.md       # GitLab workflow, commits, MRs
│   │   ├── shared-agents/      # Domain knowledge agents (symlinked)
│   │   │   ├── ocpp-protocol.agent.md
│   │   │   ├── documentation.agent.md
│   │   │   ├── etf-library.agent.md
│   │   │   └── integration-flows.agent.md
│   │   └── meta-agents/        # Framework-level agents
│   │       ├── analyzer.agent.md     # Analyzes monorepo, proposes agents
│   │       └── writer.agent.md       # Generates stack structures
│   ├── architecture/           # Framework design docs
│   └── templates/              # Boilerplate and scaffolding
└── stacks/                     # Stack-specific directories
    └── STACKNAME/              # e.g., ocpp20, python-test, cpp-firmware
  ├── agents/                # Stack-specific agents (discoverable)
  │   └── *.agent.md
  ├── docs/
  │   └── SHARED_KNOWLEDGE.md
  ├── monorepo -> /path/to/clone
  └── STACKNAME.code-workspace
```

## Three-Tier Agent System

1. **Stack-specific** (`stacks/STACKNAME/agents/`): Only for this stack’s concerns
2. **Common** (`framework/core/common-agents/`): Optional helpers you can copy/symlink into stacks when desired
3. **Shared knowledge** (`framework/core/shared-agents/`): Optional domain agents you can copy/symlink into stacks when desired

## Critical: Agent Discovery

### The Requirement

Agents are discovered from **`agents/*.agent.md` under a workspace folder root**.

In our setup, each stack is self-contained:
- Agents live in `stacks/STACKNAME/agents/`
- The stack workspace includes `.` (stack root) and `agents`

### Workspace Configuration

The workspace must include a folder root that contains `agents`.

Recommended workspace folder configuration (paths relative to the stack workspace file):

```json
{
  "folders": [
    {
      "name": "🤖 Agents (ocpp20-rust)",
      "path": "agents"
    },
    {
      "name": "📚 Stack (ocpp20-rust)",
      "path": "."
    }
    // ... other folders
  ]
}
```

Agents will be discovered from the `agents` folder in the workspace.

### Why This Architecture?

| Benefit | Explanation |
|---------|-------------|
| **Single Source of Truth** | Agents stored inside the stack (`stacks/STACKNAME/agents/`) |
| **Multi-Clone Support** | Stack contains a `monorepo` symlink that you can point at the clone you want |
| **Portability** | Workspace uses relative paths; only the `monorepo` symlink changes per machine/clone |
| **Filtered Visibility** | Each workspace only includes agents relevant to that stack |
| **Zero Global Setup** | No global `agents` symlink farm required |

See [templates/stack-creation-template.md](templates/stack-creation-template.md) for detailed examples.

## Workflow: Creating a New Stack

### 1. Analyze a monorepo path

```
@analyzer ${env:EBEE_MONOREPO_ROOT}/services/session_service
```

Analyzer examines the code and outputs:
- Stack identification
- 3-5 proposed specialized agents
- @writer command ready to execute

### 2. Generate the stack

```
@writer create-stack stacks/session-service from ${env:EBEE_MONOREPO_ROOT}/services/session_service with agents: @session-state @transaction-lifecycle @metrics
```

Writer creates:
- `stacks/session-service/` directory
- Agent files in `agents/`
- Workspace file with monorepo folders
- A stack-local `monorepo/` symlink (created by the generated commands)
- Initial SHARED_KNOWLEDGE.md

### 3. Open the workspace

```bash
code stacks/session-service/session-service.code-workspace
```

Only relevant agents appear in the workspace.

## Multi-Clone Support

Switch clones by updating the stack-local `monorepo` symlink:

```bash
ln -snf "$HOME/0_git/feature-123-clone" stacks/STACKNAME/monorepo
code stacks/STACKNAME/STACKNAME.code-workspace
```

Workspaces reference service paths via `monorepo/...` so they don’t depend on `${env:...}` expansion.

## Optional: Common/Shared Agents

If you want common/shared agents available in a stack, you can copy or symlink them into `stacks/STACKNAME/agents/`.
