# Custom GitHub Copilot Agents Framework

This framework provides **stack-based specialized agents** with filtered agent availability - only relevant agents appear when you open a workspace.

## 🚀 Quick Start

| I want to... | Workspace to open | Agents available |
|-------------|-------------------|------------------|
| **USE the framework** (create stacks) | `copilot-agents.code-workspace` | @analyzer, @writer |
| **DEVELOP the framework** (maintain agents) | `stacks/meta-agents/meta-agents.code-workspace` | @meta-maintainer, @stack-validator, etc. |

See [GETTING_STARTED.md](GETTING_STARTED.md) for detailed workflows.

## Two Modes of Operation

### 🔧 USING the Framework (Start Here)

**Open the main workspace:**
```bash
code copilot-agents.code-workspace
```

**Available agents:**
- **@analyzer** - Analyzes your project and recommends specialized agents
- **@writer** - Generates complete stack directories with agent definitions

**Workflow:**

**1. Analyze a monorepo path to get agent recommendations:**
```
@analyzer ${env:EBEE_MONOREPO_ROOT}/services/session_service
```

**2. Generate a complete stack with proposed agents:**
```
@writer create-stack stacks/session-service from ${env:EBEE_MONOREPO_ROOT}/services/session_service with agents: @session-state @transaction-lifecycle
```

**3. Open the generated workspace:**
```bash
code stacks/session-service/session-service.code-workspace
```

Only the 3-5 agents relevant to session-service appear in Copilot chat.

### 🛠️ DEVELOPING the Framework

**For maintaining/updating the framework itself:**
```bash
code stacks/meta-agents/meta-agents.code-workspace
```

See the [meta-agents stack README](stacks/meta-agents/README.md) for details on framework development agents.

## Multi-Clone Support

For working across multiple monorepo clones, point the stack-local `monorepo` symlink at the clone you want:

```bash
ln -snf "$HOME/0_git/0_ebee_meta_projects/monorepo" stacks/session-service/monorepo
code stacks/session-service/session-service.code-workspace
```

See [docs/multi-clone-setup.md](docs/multi-clone-setup.md) for details.

## Repository Structure

```
~/copilot-agents/
├── framework/                   # 🏗️ Reusable framework components
│   ├── core/                   # Agent storage
│   │   ├── common-agents/      # Agents in ALL stacks (symlinked)
│   │   │   ├── coordinator.agent.md  # Cross-stack routing
│   │   │   └── gitlab.agent.md       # GitLab workflow
│   │   ├── shared-agents/      # Domain knowledge (symlinked)
│   │   │   ├── ocpp-protocol.agent.md
│   │   │   ├── documentation.agent.md
│   │   │   ├── etf-library.agent.md
│   │   │   └── integration-flows.agent.md
│   │   └── meta-agents/        # Framework-level agents
│   │       ├── analyzer.agent.md     # Proposes stack agents
│   │       └── writer.agent.md       # Generates stacks
│   ├── architecture/           # Framework design docs (maintainers)
│   │   ├── README.md
│   │   ├── stack-architecture.md
│   │   ├── structure.md
│   │   ├── migration.md
│   │   └── symlink-reference.md
│   └── templates/              # Boilerplate and scaffolding
│       ├── README.md
│       └── stack-creation-template.md
├── stacks/                      # Stack-specific directories
│   └── STACKNAME/
│       ├── .github/agents/       # Stack agents (discoverable)
│       ├── docs/
│       ├── monorepo -> /path/to/clone
│       └── STACKNAME.code-workspace
└── docs/                        # User guides and references
    ├── usage-guide.md
    ├── coordinator-usage.md
    ├── multi-clone-setup.md
    └── stack-map.md
```

## Three-Tier Agent System

1. **Stack-specific** - Stored in `stacks/STACKNAME/.github/agents/`
2. **Common** - Stored in `framework/core/common-agents/` (optionally added per stack)
3. **Shared knowledge** - Stored in `framework/core/shared-agents/` (optionally added per stack)

## Migrating Old Workspace Files

Legacy workspace files in `workspaces/` still use the old structure. To migrate:

1. Use `@analyzer` on the monorepo path
2. Use `@writer` with recommended agents
3. Archive old workspace file

Agents available:
- `@meta-analyzer`, `@meta-writer`, `@coordinator`
- Future: `@docs-architect`, `@markdown-expert`

## How Agents Work

### Meta-Agents (Available in all workspaces)

**@meta-analyzer** - Analyzes your project and recommends specialized agents
- Auto-search mode: Reads files, detects patterns, proposes agents
- Manual input mode: Asks you about your needs

**@meta-writer** - Generates complete agent definition files
- Takes agent specs from @meta-analyzer or user requirements
- Creates production-ready `.md` files following best practices
- Includes commands, examples, boundaries

**@coordinator** - Routes questions across stacks
- Knows which specialist handles what domain
- Provides workspace switching instructions
- Formats cross-stack queries

### Creating Your First Specialist Agent

**Step 1: Analyze**
```
@meta-analyzer --auto-search
```

Example output:
```markdown
# Recommended Agents for OCPP20

1. @rust-expert - General Rust patterns
2. @async-tokio - Tokio runtime, cancellation safety
3. @ocpp-protocol - OCPP 2.0 state machines
4. @grpc-integration - tonic RPC services
```

**Step 2: Generate**
```
@meta-writer generate @async-tokio agent for Rust with tokio expertise
```

**Step 3: Save**
Save the output to `.github/agents/async-tokio.agent.md`

**Step 4: Use**
```
@async-tokio how do I handle cancellation in a select! block?
```

## Cross-Stack Coordination

When working across stacks, agents delegate to each other:

**Example: Adding a feature spanning Rust + Python**

1. Open `rust-ebee.code-workspace`
2. Ask `@coordinator I need to add diagnostics in Rust and test it in Python`
3. Follow the step-by-step routing:
   - `@grpc-integration` defines the protobuf
   - `@async-tokio` implements the service
   - Switch to `python-test.code-workspace`
   - `@pytest-integration` creates integration tests

Agents reference `shared-context.md` for common protocols, message formats, and interfaces.

## Best Practices from 2,500+ Repositories

This agent library follows proven patterns:

✅ **Specialists over generalists** - Each agent has a focused role
✅ **Commands early** - Executable commands with flags
✅ **Code examples over descriptions** - Real snippets showing patterns
✅ **Three-tier boundaries** - Always/Ask/Never prevents accidents
✅ **Specific stack details** - Exact versions and dependencies

❌ **Avoid vague helpers** - No "helpful coding assistant" agents
❌ **No abstract descriptions** - Always include concrete examples
❌ **Never skip boundaries** - Define what agents should never touch

## Shared Context

All agents read `shared-context.md` for:
- ebee monorepo structure
- Cross-stack code style rules (from `/monorepo/AGENTS.md`)
- Protobuf/gRPC interfaces
- OCPP 2.0 domain knowledge
- Actor pattern conventions
- Build commands per stack

## Git Integration

This repository is separate from the ebee monorepo:
- **ebee monorepo**: `/home/anton.kress/0_git/0_ebee_meta_projects/monorepo/`
- **Agent library**: `~/copilot-agents/` (this repository)

Agents cannot modify the ebee monorepo's `.gitignore`, workspace files, or `.github/` directory.

Workspace files in this repository reference monorepo paths, allowing agents to work with code while staying outside the monorepo's git control.

## Next Steps

### Immediate
1. ✅ Meta-agents created (analyzer, writer, coordinator)
2. ✅ Workspace files created for each stack
3. ✅ Shared context documented

### To generate
1. Open `rust-ebee.code-workspace`
2. Run `@meta-analyzer` to get recommendations
3. Use `@meta-writer` to generate recommended agents
4. Save agents to `.github/agents/`

### Recommended first agents
- `@rust-expert` - Rust ownership, traits, error handling
- `@async-tokio` - Async patterns, cancellation safety
- `@ocpp-protocol` - OCPP 2.0 domain knowledge
- `@pytest-integration` - Python integration testing

## Learn More

### User Guides (docs/)

- [docs/usage-guide.md](docs/usage-guide.md) - Agent usage patterns and workflows
- [docs/coordinator-usage.md](docs/coordinator-usage.md) - Cross-stack coordination guide
- [docs/multi-clone-setup.md](docs/multi-clone-setup.md) - Multi-clone configuration
- [docs/stack-map.md](docs/stack-map.md) - Monorepo structure reference

### Architecture Documentation (architecture/)

- [architecture/stack-architecture.md](architecture/stack-architecture.md) - Complete architecture overview
- [architecture/structure.md](architecture/structure.md) - Repository structure details
- [architecture/migration.md](architecture/migration.md) - Migration guides and patterns
- [architecture/symlink-reference.md](architecture/symlink-reference.md) - Symlink quick reference
- [architecture/README.md](architecture/README.md) - Navigation guide for maintainers

### Templates and Boilerplate (templates/)

- [templates/stack-creation-template.md](templates/stack-creation-template.md) - Template for new stacks
- [templates/README.md](templates/README.md) - Template usage conventions

### Additional Resources


- [GitHub Blog: How to write a great agents.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- [shared-context.md](.github/agents/shared-context.md) - ebee-specific knowledge
## License

SPDX-License-Identifier: LicenseRef-ebee-proprietary
Copyright: Bender Industries GmbH & co. KG and affiliates

---

## Stack Creation Flow (Complete Process)

This section clarifies the **full lifecycle** of creating a new stack, ensuring agents are properly discoverable.

### Step 1: Analyze the Target Codebase

```bash
@analyzer ${env:EBEE_MONOREPO_ROOT}/path/to/service
```

The analyzer examines the codebase and outputs a complete `@writer` command with recommended agents.

### Step 2: Execute Stack Creation

Execute the command provided by analyzer:

```bash
@writer create-stack stacks/my-stack from /path/to/service with agents: @agent1, @agent2, @agent3
```

### Step 3: Execute Generated Commands

The @writer outputs shell commands. Execute them:

```bash
# Create directory structure
mkdir -p stacks/my-stack/{.github/agents,docs}

# Create agent files (examples provided)
cat > stacks/my-stack/.github/agents/agent1.agent.md << 'AGENT'
# ... agent content ...
AGENT

# Create stack-local monorepo symlink (stable workspace paths)
ln -s "${EBEE_MONOREPO_ROOT}" stacks/my-stack/monorepo

# Create workspace file
cat > ~/copilot-agents/stacks/my-stack/my-stack.code-workspace << 'WS'
{
  "folders": [
    {
      "name": "🤖 Agents (my-stack)",
      "path": ".github/agents"
    },
    {
      "name": "📦 Service Code",
      "path": "monorepo/path/to/service"
    },
    {
      "name": "📚 Stack (my-stack)",
      "path": "."
    }
  ]
}
WS

# Create documentation
cat > stacks/my-stack/README.md << 'README'
# My Stack
...
README

cat > stacks/my-stack/docs/SHARED_KNOWLEDGE.md << 'SHARED'
# Shared Knowledge
...
SHARED
```

### Step 4: Verify and Open Workspace

```bash
# Verify agents exist
ls -la stacks/my-stack/.github/agents/ | grep agent1

# Open the workspace
code ~/copilot-agents/stacks/my-stack/my-stack.code-workspace
```

### Step 5: Confirm Agents Are Discoverable

In VS Code with the workspace open:
1. Open Copilot chat (@)
2. Type `@agent1` - should autocomplete
3. Type `@gitlab` - should show common agent
4. Type `@ocpp-protocol` - should show shared agent

If agents don't appear, troubleshoot:
- [ ] Agent files exist: `ls -la stacks/my-stack/.github/agents/`
- [ ] Workspace includes stack root `.` and `.github/agents`
- [ ] `stacks/my-stack/monorepo` symlink points to the correct clone

## FAQ: Symlinks and Discovery

**Q: Do I need symlinks for agents?**
A: No. Store agents directly in `stacks/STACKNAME/.github/agents/`.

**Q: Can I use local `agents/` folder?**
A: Only if it is `.github/agents/` under a workspace folder root. We standardize on `stacks/STACKNAME/.github/agents/`.

**Q: What if I have multiple monorepo clones?**
A: Point `stacks/STACKNAME/monorepo` at the clone you want to work on (update with `ln -snf /path/to/clone stacks/STACKNAME/monorepo`).

**Q: How do I make agents stack-specific?**
A: Store them in `stacks/STACKNAME/agents/`. Only symlink them in the monorepo if you want that stack to use them. Other stacks won't have symlinks, so agents won't appear in their workspaces.

**Q: Can I symlink agents from one stack to another?**
A: Yes! If two stacks share agents, symlink the same agent in both stack directories. It's still one source file, multiple discovery paths.

## Troubleshooting

### Agents not appearing in Copilot chat

**Check 1: Agent files exist**
```bash
ls -la stacks/my-stack/.github/agents/
```

**Check 2: Workspace paths are relative**
```bash
cat stacks/my-stack/my-stack.code-workspace | grep -E '"path": "\.github/agents"|"path": "monorepo/'
```

**Check 3: `monorepo/` symlink points to the correct clone**
```bash
ls -la stacks/my-stack/monorepo
```

**Check 4: Reload VS Code**
- Command Palette → "Developer: Reload Window"

### Symlink creation failed

**Issue: "monorepo symlink not found"**
```bash
ln -snf "${EBEE_MONOREPO_ROOT}" stacks/my-stack/monorepo
```

## References

> For complete documentation navigation, see the [Learn More](#learn-more) section above.


- [architecture/stack-architecture.md](architecture/stack-architecture.md) - Complete architecture overview
- [templates/stack-creation-template.md](templates/stack-creation-template.md) - Template for new stacks
- [writer.agent.md](writer.agent.md) - Meta-agent that generates stacks
- [analyzer.agent.md](analyzer.agent.md) - Meta-agent that analyzes codebases
