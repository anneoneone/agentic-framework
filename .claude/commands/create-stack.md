# Create Stack

Create a new agent stack for a project. This orchestrates the analyzer and writer workflow.

## Input

The user provides either:
- A path to an existing project: `$ARGUMENTS`
- A description of a new project: `$ARGUMENTS`

## Workflow

### Step 1: Analyze

If the argument is a file path that exists:
1. Read project files (package.json, Cargo.toml, pyproject.toml, go.mod, etc.)
2. Scan directory structure to understand architecture
3. Identify technologies, frameworks, patterns, and testing strategy
4. Check for existing documentation (README.md, docs/)

If the argument is a project description:
1. Ask clarifying questions about: programming language(s), frameworks, project type, deployment target
2. Determine the optimal tech stack based on requirements

### Step 2: Recommend agents

Based on the analysis:
1. Propose 3-5 specialist agents with justifications
2. List which common agents will be symlinked (coordinator, planner, gitlab)
3. Suggest which MCP servers each agent needs
4. Present recommendations to user for approval

Format:
```
## Stack Analysis: [name]
- Tech Stack: [languages, frameworks]
- Project Type: [type]

## Recommended Agents
1. @[name] - [purpose] (justification: [why])
2. @[name] - [purpose] (justification: [why])
...

## Common Agents (auto-included)
- coordinator, planner, gitlab
```

Wait for user confirmation before proceeding.

### Step 3: Create stack

After user approves:
1. Create directory structure:
   ```
   stacks/[stack-name]/
     agents/
     plans/
     docs/knowledge/
   ```
2. Generate each specialist agent using the template at `framework/templates/specialist-agent.template.md`
3. Symlink common agents:
   ```bash
   ln -sf ../../../framework/core/common-agents/coordinator.agent.md stacks/[stack-name]/agents/
   ln -sf ../../../framework/core/common-agents/planner.agent.md stacks/[stack-name]/agents/
   ln -sf ../../../framework/core/common-agents/gitlab.agent.md stacks/[stack-name]/agents/
   ```
4. Create `stacks/[stack-name]/docs/knowledge/index.md` with basic structure
5. Create `stacks/[stack-name]/README.md` with stack overview

### Step 4: Validate

Run validation:
```bash
python framework/scripts/validate-agent.py --stack [stack-name]
```

Fix any errors before presenting the result.

### Step 5: Initialize knowledge

If memento-knowledge MCP is available:
```
memento-knowledge.add_decision(
  content="Created stack [stack-name] with agents: [list]",
  stack="[stack-name]",
  agent="@analyzer"
)
```

### Output

Present a summary:
```
Stack created: stacks/[stack-name]/
- [N] specialist agents
- [N] common agents (symlinked)
- Knowledge directory initialized
- Validation: [result]
```
