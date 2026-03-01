# Getting Started with Copilot Agents Framework

## Which Workspace Should I Open?

### 🔧 I want to USE the framework (create new stacks)

```bash
code copilot-agents.code-workspace
```

**Agents available:**
- `@analyzer` - Analyze code and recommend agents
- `@writer` - Generate complete stack directories

**Use case:** Creating specialized agent stacks for your projects

---

### 🛠️ I want to DEVELOP the framework (maintain agents)

```bash
code stacks/meta-agents/meta-agents.code-workspace
```

**Agents available:**
- `@meta-maintainer` - Update framework components
- `@stack-validator` - Validate stack integrity
- `@template-generator` - Create agent templates
- `@migration-assistant` - Migrate legacy patterns
- `@documentation-syncer` - Sync documentation
- `@coordinator` - Route between agents
- `@gitlab` - GitLab workflows

**Use case:** Maintaining the agent framework itself

---

## Quick Workflow Examples

### Creating a New Stack (USING)

1. Open `copilot-agents.code-workspace`
2. Analyze your code:
   ```
   @analyzer /path/to/your/project
   ```
3. Generate stack:
   ```
   @writer create-stack stacks/my-stack from /path with agents: @agent1, @agent2
   ```
4. Open the new stack workspace

### Updating Framework Agents (DEVELOPING)

1. Open `stacks/meta-agents/meta-agents.code-workspace`
2. Make changes:
   ```
   @meta-maintainer update @coordinator to version 1.2 across all stacks
   ```
3. Validate:
   ```
   @stack-validator check all stacks
   ```

---

## Architecture Overview

```
copilot-agents/
├── copilot-agents.code-workspace    ← USING (has @analyzer, @writer)
│
├── .github/agents/                   ← Framework-level agents
│   ├── analyzer.agent.md            (for analyzing projects)
│   └── writer.agent.md              (for creating stacks)
│
├── _common/                          ← Agents shared across stacks
│   ├── coordinator.agent.md
│   └── gitlab.agent.md
│
├── _shared/                          ← Domain knowledge agents
│   └── ...
│
└── stacks/
    ├── meta-agents/
    │   ├── meta-agents.code-workspace  ← DEVELOPING (framework maintenance)
    │   └── .github/agents/
    │       ├── meta-maintainer.agent.md
    │       ├── stack-validator.agent.md
    │       ├── template-generator.agent.md
    │       ├── migration-assistant.agent.md
    │       ├── documentation-syncer.agent.md
    │       ├── coordinator.agent.md     (symlink to _common)
    │       └── gitlab.agent.md          (symlink to _common)
    │
    ├── ocpp20-rust/
    │   ├── ocpp20-rust.code-workspace  ← USER STACK
    │   └── .github/agents/
    │       ├── rust-expert.agent.md
    │       ├── ocpp-protocol.agent.md   (symlink to _shared)
    │       └── ...
    │
    └── systemtests-python/
        ├── systemtests-python.code-workspace  ← USER STACK
        └── .github/agents/
            ├── python-expert.agent.md
            ├── pytest-expert.agent.md
            └── ...
```

**Key points:**
- **Top-level workspace** → agents for creating/analyzing (@analyzer, @writer)
- **meta-agents workspace** → agents for framework maintenance
- **User stack workspaces** → domain-specific agents for actual development

## See Also

- [README.md](README.md) - Framework overview
- [docs/usage-guide.md](docs/usage-guide.md) - Detailed usage instructions
- [stacks/meta-agents/README.md](stacks/meta-agents/README.md) - Framework development guide
- [framework/architecture/stack-architecture.md](framework/architecture/stack-architecture.md) - Architecture details
