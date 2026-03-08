# Create Stack

Create a new agent stack for a project. This orchestrates the analyzer and writer workflow.

## Input

The user provides one of:
- A path to an existing project: `/create-stack /path/to/project`
- A one-shot description: `/create-stack "project description"`
- Interview mode (greenfield): `/create-stack --interview` or `/create-stack` (no args)

## Workflow

### Step 1: Determine mode

**Path mode** — argument is a file path that exists:
1. Read project files (package.json, Cargo.toml, pyproject.toml, go.mod, etc.)
2. Scan directory structure to understand architecture
3. Identify technologies, frameworks, patterns, and testing strategy
4. Check for existing documentation (README.md, docs/)

**Description mode** — argument is a non-path string:
1. Interpret the description to infer tech stack and domain
2. If key details are ambiguous, ask one focused clarifying question
3. Proceed to Step 2

**Interview mode** — `--interview` flag OR no arguments provided:
1. Activate `@analyzer` interview mode (see `framework/docs/requirements-interview-design.md`)
2. Ask questions in 4 phases: Identity → Tech Stack → Architecture → Team/Scale
3. Build a `RequirementsProfile` from answers
4. Apply the answer→agent mapping table to produce recommendations
5. CLI alternative: `python framework/scripts/requirements-interview.py` then pass output here

> Use interview mode for **greenfield projects** — when no code exists yet and you want
> the framework to help you design the right agent set from requirements.

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
