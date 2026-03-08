# Update Agents

Validate and update agents in a stack to match the current template version.

## Input

`$ARGUMENTS` should be a stack name, or `--all` for all stacks.

## Workflow

### Step 1: Validate current state
```bash
python framework/scripts/validate-agent.py --stack $ARGUMENTS
```

### Step 2: Load current template

Read `framework/templates/specialist-agent.template.md` to know the expected structure.

### Step 3: For each agent with errors or warnings

1. **Missing frontmatter fields** - Add required fields (name, description) and recommended fields (version, keywords, scope, mcp_servers)
2. **Missing sections** - Add stub sections preserving existing content
3. **Version bump** - Increment version if content changed
4. **Keyword audit** - Ensure min 3 keywords, no >50% overlap with other agents

### Step 4: Re-validate
```bash
python framework/scripts/validate-agent.py --stack $ARGUMENTS
```

### Rules

- Never remove existing content - only add or restructure
- Preserve the agent's domain language and examples
- Minimal diffs - only change what validation requires
- Report changes as a summary table
