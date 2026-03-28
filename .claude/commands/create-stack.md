# Create Stack

Create a new agent stack for a project. This orchestrates the analyzer and writer workflow.

## Input

The user provides one of:
- A path to an existing project: `/create-stack /path/to/project`
- A link to an external repo: `/create-stack --link /path/to/repo [--name stack-name]`
- A one-shot description: `/create-stack "project description"`
- Interview mode (greenfield): `/create-stack --interview` or `/create-stack` (no args)

## Workflow

### Step 1: Determine mode

**Link mode** — `--link /path/to/repo` flag is present:
1. Verify the path exists on disk (fail clearly if not)
2. Derive stack name from the directory name, or use `--name` override
3. Read project files from the external path (package.json, Cargo.toml, pyproject.toml, README.md, etc.)
4. Scan directory structure to understand architecture
5. Identify technologies, frameworks, patterns, and testing strategy
6. Proceed to Step 2 (agent recommendations)

> Use link mode when the project lives in its own repository. The framework stack
> contains only agents/plans/knowledge; source files are accessed via `project/` symlink.

**Path mode** — argument is a file path that exists (no `--link` flag):
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
2. **Link mode only** — write `.stack.json` and create `project/` symlink:
   ```bash
   # Write stacks/[stack-name]/.stack.json
   {
     "stack": "[stack-name]",
     "type": "linked",
     "repo_path": "/absolute/path/to/repo",
     "repo_url": "",
     "created_at": "[ISO 8601 timestamp]"
   }

   # Create symlink
   ln -s /absolute/path/to/repo stacks/[stack-name]/project
   ```
   Then note to user: *On other machines, restore with `python framework/scripts/link-stack.py --stack [stack-name]`*

   After creating the project symlink, run the link script to wire up `.claude/` in the project repo:
   ```bash
   python framework/scripts/link-stack.py --stack [stack-name]
   ```
   This creates symlinks in the **project repo** so slash commands, agents, MCP config, and
   settings are available when the workspace is opened:
   - `<repo>/.claude/commands/` → framework `.claude/commands/`
   - `<repo>/.claude/agents/` → `stacks/[stack-name]/agents/`
   - `<repo>/.claude/settings.local.json` → framework `.claude/settings.local.json`
   - `<repo>/.mcp.json` → framework `.mcp.json`

   Also ensure `.claude/` and `.mcp.json` are in the project repo's `.gitignore`:
   ```bash
   cd /path/to/repo
   grep -q '\.claude/' .gitignore 2>/dev/null || echo '.claude/' >> .gitignore
   grep -q '\.mcp\.json' .gitignore 2>/dev/null || echo '.mcp.json' >> .gitignore
   ```
3. Generate each specialist agent using the template at `framework/templates/specialist-agent.template.md`
   - **Link mode**: Key Files paths MUST use `project/` prefix (e.g. `project/src/main.py`)
   - **Embedded/path mode**: Key Files paths are relative to `stacks/[stack-name]/`
4. Symlink common agents:
   ```bash
   ln -sf ../../../framework/core/common-agents/coordinator.agent.md stacks/[stack-name]/agents/
   ln -sf ../../../framework/core/common-agents/planner.agent.md stacks/[stack-name]/agents/
   ln -sf ../../../framework/core/common-agents/gitlab.agent.md stacks/[stack-name]/agents/
   ```
5. Create `stacks/[stack-name]/docs/knowledge/index.md` with basic structure
6. Create `stacks/[stack-name]/README.md` with stack overview
7. **Link mode only** — create a VS Code workspace file at `stacks/[stack-name]/[stack-name].code-workspace`:
   ```json
   {
     "folders": [
       { "name": "[stack-name] (project)", "path": "/absolute/path/to/repo" },
       { "name": "agentic-framework (agents & plans)", "path": "<framework root>" }
     ],
     "settings": { "files.exclude": { "**/node_modules": true, "**/.git": true } }
   }
   ```
   Open with: `code stacks/[stack-name]/[stack-name].code-workspace`

### Step 4: Validate

Run validation:
```bash
python framework/scripts/validate-agent.py --stack [stack-name]
```

Fix any errors before presenting the result.

### Step 5: Extract and initialize knowledge

This step ensures all discovered knowledge is persisted to JSONL files AND the Neo4j knowledge graph.

**For linked/path stacks** (existing project was analyzed):

During analysis in Step 1, you identified architecture, tech stack, endpoints,
env vars, and patterns. Write this knowledge to JSONL files before initializing Neo4j:

1. Write `stacks/[stack-name]/docs/knowledge/extracted-decisions.jsonl`:
   - Tech stack choices (languages, frameworks) with rationale
   - Architecture decisions discovered during analysis
   - Testing strategy
   - Each line: `{"type":"decision","content":"...","stack":"[stack-name]","date":"[ISO date]","agent":"@analyzer"}`

2. Write `stacks/[stack-name]/docs/knowledge/extracted-learnings.jsonl`:
   - Architecture patterns (e.g., "Uses layered architecture with service/repo split")
   - Key conventions (naming, file organization)
   - Each line: `{"type":"learning","content":"...","category":"architecture","stack":"[stack-name]","date":"[ISO date]","agent":"@analyzer"}`

3. Write `stacks/[stack-name]/docs/knowledge/api-endpoints.jsonl` (if applicable):
   - All discovered API routes / gRPC services
   - Each line: `{"method":"GET","path":"/api/...","purpose":"...","auth":true}`

4. Write `stacks/[stack-name]/docs/knowledge/env-vars.jsonl` (if applicable):
   - All discovered environment variables
   - Each line: `{"name":"VAR_NAME","purpose":"...","value":""}`

5. Initialize Neo4j:
   ```bash
   python framework/scripts/init-stack-neo4j.py --stack [stack-name]
   ```

**For fresh stacks** (interview/description mode):

1. Save the RequirementsProfile to `stacks/[stack-name]/requirements-profile.json`
2. Initialize Neo4j with the profile as seed:
   ```bash
   python framework/scripts/init-stack-neo4j.py --stack [stack-name] \
     --profile stacks/[stack-name]/requirements-profile.json
   ```

**Fallback**: If the script fails or Neo4j is unavailable, the JSONL files still exist and a
`.neo4j-init-pending` marker is created. The user can retry later with:
```bash
python framework/scripts/init-stack-neo4j.py --stack [stack-name]
```

If the CLI script is unavailable, fall back to:
```
memento-knowledge.init_stack(stack="[stack-name]")
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
